"""Follow-ups, saved plans, check-ins, the weekly review, calendar export, the
allowance figure, running summaries, memory provenance and "about me"."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.conversations import service as convo_service
from app.core.config import settings
from app.db.models import CheckIn, Conversation, FollowUp, Plan, SharedMemory, User
from app.llm.base import LLMResult
from app.memory.llm_extraction import (
    CheckInItem,
    Event,
    TurnAnalysis,
    analyze_turn,
    worth_analyzing,
)
from app.memory.pasted import is_about_me
from app.tracking import plans as plan_service
from app.tracking import service as tracking
from app.users.service import get_or_create_demo_user

PLAN = """# 3-day revision plan

| Day | Focus |
|---|---|
| Day 1 | Thermodynamics past paper |
| Day 2 | Fluids: weak topics |
| Day 3 | Full mock exam |

Want me to adjust it?"""


def _today() -> date:
    return datetime.now(UTC).date()


def _conversation_with_plan(db, agent="study"):
    user = get_or_create_demo_user(db)
    user.timezone = "UTC"
    convo = convo_service.create_conversation(db, user.id, agent)
    convo_service.add_message(db, convo, "user", "Make me a 3-day revision plan")
    reply = convo_service.add_message(db, convo, "assistant", PLAN)
    db.commit()
    return user, convo, reply


# --- plans ---------------------------------------------------------------------------


def test_steps_are_read_from_tables_lists_and_day_lines():
    title, steps = plan_service.parse_steps(PLAN)
    assert title == "3-day revision plan"
    assert steps == [
        "Day 1 — Thermodynamics past paper",
        "Day 2 — Fluids: weak topics",
        "Day 3 — Full mock exam",
    ]
    _, listed = plan_service.parse_steps("Try this:\n- **Warm up** 10 min\n2. Squats\nDay 3: rest")
    assert listed == ["Warm up 10 min", "Squats", "Day 3: rest"]


def test_saying_save_this_plan_keeps_the_previous_reply(client, db):
    _, convo, reply = _conversation_with_plan(db)
    body = client.post(
        "/api/agents/study/chat",
        json={"message": "Great, save this plan", "conversation_id": convo.id},
    ).json()
    assert body["plans"][0]["title"] == "3-day revision plan"
    assert body["plans"][0]["steps"] == 3
    plan = db.scalar(select(Plan))
    assert plan.source_message_id == reply.id
    assert [s.due_on for s in plan.steps] == [_today() + timedelta(days=i) for i in range(3)]


def test_progress_is_marked_from_chat_and_the_plan_closes_when_done(client, db):
    _, convo, _ = _conversation_with_plan(db)
    client.post(
        "/api/agents/study/chat", json={"message": "save this plan", "conversation_id": convo.id}
    )
    body = client.post(
        "/api/agents/study/chat",
        json={"message": "Done with day 1 and finished day 2", "conversation_id": convo.id},
    ).json()
    assert [p["text"] for p in body["plan_progress"]] == [
        "Day 1 — Thermodynamics past paper",
        "Day 2 — Fluids: weak topics",
    ]
    client.post(
        "/api/agents/study/chat", json={"message": "did day 3", "conversation_id": convo.id}
    )
    db.expire_all()
    assert db.scalar(select(Plan)).status == "done"


def test_the_agent_sees_its_saved_plan_and_progress(client, db):
    user, convo, _ = _conversation_with_plan(db)
    client.post(
        "/api/agents/study/chat", json={"message": "save this plan", "conversation_id": convo.id}
    )
    sections, _ = tracking.context_sections(
        db, user.id, agent_id="study", is_leo=False, today=_today()
    )
    text = "\n".join(sections)
    assert "3-day revision plan: 0/3 done; next: Day 1" in text
    other, _ = tracking.context_sections(
        db, user.id, agent_id="fitness", is_leo=False, today=_today()
    )
    assert other == []


def test_plans_api_save_tick_and_calendar(client, db):
    _, _, reply = _conversation_with_plan(db)
    plan = client.post("/api/plans", json={"message_id": reply.id}).json()
    step = plan["steps"][0]
    ticked = client.patch(f"/api/plans/{plan['id']}/steps/{step['id']}", json={"done": True})
    assert ticked.json()["done"] == 1
    ics = client.get(f"/api/plans/{plan['id']}/calendar.ics")
    assert ics.headers["content-type"].startswith("text/calendar")
    assert ics.text.count("BEGIN:VEVENT") == 2  # the ticked step is not exported
    assert "Fluids: weak topics" in ics.text
    assert client.post("/api/plans", json={"message_id": "nope"}).status_code == 404


# --- follow-ups and check-ins ------------------------------------------------------------


class Stub:
    name = "stub"

    def __init__(self, payload):
        self.payload = json.dumps(payload)
        self.systems: list[str] = []
        self.messages: list[str] = []

    async def complete(self, **kwargs):
        self.systems.append(kwargs["system"])
        self.messages.append(kwargs["messages"][0].content)
        return LLMResult(text=self.payload, model="stub", usage={})


def test_the_analyzer_returns_validated_events_and_checkins():
    today = date(2026, 9, 25)
    stub = Stub(
        {
            "facts": [],
            "events": [
                {
                    "title": "Interview at Stripe",
                    "date": "2026-10-01",
                    "agent": "career",
                    "sensitive": False,
                },
                # The model says not sensitive; the keyword backstop overrules it.
                {"title": "Therapy session", "date": "2026-10-02", "sensitive": False},
                {"title": "Old exam", "date": "2026-09-01", "agent": "study"},
                {"title": "Far away", "date": "2030-01-01", "agent": None},
            ],
            "checkins": [
                {
                    "agent": "fitness",
                    "text": "ran 5k",
                    "amount": 5,
                    "unit": "km",
                    "sensitive": False,
                },
                {
                    "agent": "nobody",
                    "text": "read 20 pages",
                    "amount": True,
                    "unit": "",
                    "sensitive": False,
                },
            ],
        }
    )
    result = asyncio.run(
        analyze_turn(
            "I ran 5k and my Stripe interview is next Thursday",
            agent_id="career",
            provider=stub,
            model="stub",
            today=today,
        )
    )
    assert [(e.title, e.due_on, e.agent_id, e.stored) for e in result.events] == [
        ("Interview at Stripe", date(2026, 10, 1), "career", True),
        ("Therapy session", date(2026, 10, 2), "career", False),  # sensitive: withheld
    ]
    assert [(c.agent_id, c.text, c.amount, c.unit) for c in result.checkins] == [
        ("fitness", "ran 5k", 5.0, "km"),
        ("career", "read 20 pages", None, None),
    ]
    assert '"events"' in stub.systems[0]


def test_dated_and_done_messages_are_analysed():
    ask = {"agent_id": "career", "goals_allowed": False}
    assert worth_analyzing("Interview next Thursday", **ask)
    assert worth_analyzing("ran 5k this morning", **ask)
    assert not worth_analyzing("What's a good opening line?", **ask)


def _analysis(**parts):
    async def fake(message, **kwargs):
        return TurnAnalysis(**parts)

    return fake


def test_followups_and_checkins_are_stored_from_a_turn(client, db, monkeypatch):
    import app.agents.runtime as runtime_module

    monkeypatch.setattr(settings, "memory_extraction", "llm")
    due = _today() + timedelta(days=6)
    monkeypatch.setattr(
        runtime_module,
        "analyze_turn",
        _analysis(
            events=[Event("career", "Interview at Stripe", due)],
            checkins=[CheckInItem("fitness", "ran 5k", 5.0, "km")],
        ),
    )
    body = client.post("/api/agents/career/chat", json={"message": "I have an interview"}).json()
    assert body["followups"][0]["stored"] is True
    assert body["checkins"][0]["text"] == "ran 5k"
    # Mentioned again: still one follow-up.
    again = client.post("/api/agents/career/chat", json={"message": "I have that interview"})
    assert again.json()["followups"][0]["reason"] == "already in your follow-ups"
    assert len(list(db.scalars(select(FollowUp)))) == 1
    assert db.scalar(select(CheckIn)).logged_on == _today()


def test_with_memory_off_nothing_is_tracked_automatically(client, db, monkeypatch):
    import app.agents.runtime as runtime_module

    monkeypatch.setattr(settings, "memory_extraction", "llm")
    seen = {}

    async def fake(message, **kwargs):
        seen.update(kwargs)
        return TurnAnalysis()

    monkeypatch.setattr(runtime_module, "analyze_turn", fake)
    user = get_or_create_demo_user(db)
    user.memory_auto = False
    db.commit()
    client.post("/api/agents/career/chat", json={"message": "I have an interview Thursday"})
    assert seen["learn_facts"] is False


def test_a_passed_followup_is_asked_about_once(client, db):
    user = get_or_create_demo_user(db)
    user.timezone = "UTC"
    db.add(
        FollowUp(
            user_id=user.id,
            agent_id="career",
            title="Stripe interview",
            due_on=_today() - timedelta(days=1),
        )
    )
    db.commit()
    first = tracking.context_sections(db, user.id, agent_id="career", is_leo=False, today=_today())
    assert "ask how it went" in "\n".join(first[0])
    client.post("/api/agents/career/chat", json={"message": "hi"})
    db.expire_all()
    second = tracking.context_sections(db, user.id, agent_id="career", is_leo=False, today=_today())
    assert "ask how it went" not in "\n".join(second[0])


def test_followups_are_leos_and_their_owners_only(db):
    user = get_or_create_demo_user(db)
    db.add(
        FollowUp(
            user_id=user.id,
            agent_id="career",
            title="Stripe interview",
            due_on=_today() + timedelta(days=3),
        )
    )
    db.commit()

    def sees(agent, leo=False):
        sections, _ = tracking.context_sections(
            db, user.id, agent_id=agent, is_leo=leo, today=_today()
        )
        return "Stripe interview" in "\n".join(sections)

    assert sees("career") and sees("modeer", leo=True) and not sees("fitness")


def test_followups_api_and_calendar(client):
    due = (_today() + timedelta(days=10)).isoformat()
    made = client.post("/api/followups", json={"title": "Dentist, 3pm", "due_on": due}).json()
    assert client.get("/api/followups").json()[0]["title"] == "Dentist, 3pm"
    ics = client.get("/api/followups/calendar.ics").text
    assert "SUMMARY:Dentist\\, 3pm" in ics and f"DTSTART;VALUE=DATE:{due.replace('-', '')}" in ics
    done = client.patch(f"/api/followups/{made['id']}", json={"status": "done"}).json()
    assert done["status"] == "done"
    assert client.delete(f"/api/followups/{made['id']}").status_code == 204


def test_briefing_shows_what_is_coming_and_what_just_passed(client, db):
    user = get_or_create_demo_user(db)
    user.timezone = "UTC"
    db.add_all(
        [
            FollowUp(
                user_id=user.id,
                agent_id="career",
                title="Stripe interview",
                due_on=_today() + timedelta(days=2),
            ),
            FollowUp(
                user_id=user.id,
                agent_id="study",
                title="Thermo exam",
                due_on=_today() - timedelta(days=1),
            ),
        ]
    )
    db.commit()
    items = client.get("/api/briefings/today").json()["items"]
    texts = [i["text"] for i in items]
    assert texts[0] == "How did it go? Thermo exam"
    assert "Stripe interview" in texts


def test_weekly_review_counts_what_happened(client, db):
    user = get_or_create_demo_user(db)
    user.timezone = "UTC"
    db.add(CheckIn(user_id=user.id, agent_id="fitness", text="ran 5k", logged_on=_today()))
    db.add(
        FollowUp(
            user_id=user.id,
            agent_id="career",
            title="Stripe interview",
            due_on=_today() + timedelta(days=3),
        )
    )
    db.commit()
    review = client.get("/api/briefings/week").json()
    assert review["checkins"] == {"fitness": 1}
    assert "1 check-in logged" in review["summary"] and "Stripe interview" in review["summary"]


# --- allowance, summaries -------------------------------------------------------------------


def test_the_allowance_is_reported(client, monkeypatch):
    monkeypatch.setattr(settings, "account_daily_token_budget", 100000)
    before = client.get("/api/usage/me").json()
    assert before["limit"] == 100000 and before["messages_left"] == 25
    body = client.post("/api/agents/study/chat", json={"message": "hello"}).json()
    assert body["allowance"]["used"] > 0
    assert client.get("/api/usage/me").json()["remaining"] < 100000


def test_old_turns_are_folded_into_a_running_summary(client, db, monkeypatch):
    monkeypatch.setattr(settings, "memory_extraction", "llm")
    user = get_or_create_demo_user(db)
    convo = convo_service.create_conversation(db, user.id, "study")
    for i in range(12):
        convo_service.add_message(db, convo, "user", f"question {i}")
        convo_service.add_message(db, convo, "assistant", f"answer {i}")
    db.commit()
    client.post("/api/agents/study/chat", json={"message": "and now?", "conversation_id": convo.id})
    db.expire_all()
    convo = db.get(Conversation, convo.id)
    assert convo.summary and convo.summary_count == 14  # 26 messages, 12 kept
    body = client.post(
        "/api/agents/study/chat", json={"message": "next", "conversation_id": convo.id}
    ).json()
    assert body["context"]["history_messages"] <= 14


# --- memory provenance, about me --------------------------------------------------------------


def test_why_do_you_know_this_and_undo(client, db, monkeypatch):
    import app.agents.runtime as runtime_module
    from app.memory.extraction import Candidate

    monkeypatch.setattr(settings, "memory_extraction", "llm")

    def fact(value):
        return Candidate("shared", None, "context", "location", value, 0.9, False, True, "ok")

    for value in ("Cairo", "Giza"):
        monkeypatch.setattr(runtime_module, "analyze_turn", _analysis(facts=[fact(value)]))
        client.post("/api/agents/modeer/chat", json={"message": f"I live in {value}"})
    row = db.scalar(select(SharedMemory).where(SharedMemory.key == "location"))
    source = client.get(f"/api/memory/shared/{row.id}/source").json()
    assert source["learned_from"]["excerpt"] == "I live in Giza"
    assert source["learned_from"]["agent_id"] == "modeer"
    assert source["history"][-1]["value"] == "Cairo"

    undone = client.post(f"/api/memory/shared/{row.id}/undo").json()
    assert undone["value"] == "Cairo" and undone["history"] == []
    assert client.post(f"/api/memory/shared/{row.id}/undo").status_code == 409
    assert client.get("/api/memory/shared/nope/source").status_code == 404


def test_about_me_text_is_learned_even_when_it_looks_pasted():
    cv = "This is about me:\n\n> I am studying naval architecture at Chalmers."
    assert is_about_me(cv) and not is_about_me("Here's my boss's email: hi")
    stub = Stub({"facts": []})
    asyncio.run(analyze_turn(cv, agent_id="modeer", provider=stub, model="stub"))
    assert "naval architecture" in stub.messages[0]


def test_about_me_endpoint(client, db):
    body = client.post(
        "/api/users/me/about", json={"text": "I am studying naval architecture at Chalmers."}
    ).json()
    assert any(
        "naval architecture" in c["value"] and c["stored"] for c in body["memory_candidates"]
    )


# --- account data --------------------------------------------------------------------------


def test_export_includes_and_deletion_removes_tracked_data(client, db):
    _, convo, reply = _conversation_with_plan(db)
    client.post("/api/plans", json={"message_id": reply.id})
    client.post("/api/followups", json={"title": "Exam", "due_on": _today().isoformat()})
    export = client.get("/api/users/me/export").json()
    assert export["plans"][0]["steps"] and export["followups"][0]["title"] == "Exam"
    assert "checkins" in export
    assert client.post("/api/users/me/delete", json={"confirm": "DELETE"}).status_code == 204
    db.expire_all()
    assert db.scalar(select(Plan)) is None and db.scalar(select(FollowUp)) is None
    assert db.scalar(select(User)) is None


def test_only_a_request_to_keep_a_plan_saves_one():
    for asked in (
        "save this plan",
        "keep that schedule",
        "make me a plan and save it",
        "احفظ هذه الخطة",
    ):
        assert plan_service.asks_to_save(asked), asked
    for not_asked in (
        "I want to save money with a plan",
        "save this for my trip budget",
        "don't save this plan",
        "track my progress on this plan",
        "should I save this plan?",
    ):
        assert not plan_service.asks_to_save(not_asked), not_asked


def test_progress_is_not_ticked_by_questions_or_negations():
    named = plan_service.progress_named
    assert named("Done with day 1 and finished day 2") == [("day", 1), ("day", 2)]
    assert named("day 3 done!") == [("day", 3)]
    assert named("خلصت اليوم ٣") == [("day", 3)]
    for not_done in (
        "I have not finished day 3 yet",
        "I'm not done with day 3",
        "how did week 2 go for you?",
        "did 3 sets of 10, day 4 of my streak",
        "I didn't finish week 1",
    ):
        assert named(not_done) == [], not_done


def test_day_headings_weekdays_and_ranges_are_steps_with_dates():
    reply = """# Strength block
## Day 1 — Upper
- Push-ups 3x10
- Rows 3x10
## Day 2 (Wed) — Lower
- Squats 3x8
"""
    title, steps = plan_service.parse_steps(reply)
    assert title == "Strength block"
    assert steps == ["Day 1 — Upper: Push-ups 3x10; Rows 3x10", "Day 2 (Wed) — Lower: Squats 3x8"]
    monday = date(2026, 9, 28)
    assert plan_service._due("Day 2 (Wed) — Lower", monday) == date(2026, 9, 30)
    assert plan_service._due("Fri — Full body", monday) == date(2026, 10, 2)
    assert plan_service._due("Week 2 · Mon", monday) == date(2026, 10, 5)
    assert plan_service._due("Days 3–4: review", monday) == date(2026, 9, 30)


def test_a_missed_plan_is_shifted_not_left_overdue(client, db):
    _, convo, reply = _conversation_with_plan(db)
    plan = client.post("/api/plans", json={"message_id": reply.id}).json()
    row = db.get(Plan, plan["id"])
    plan_service.reschedule(row, _today() - timedelta(days=5))
    db.commit()
    body = client.post(
        "/api/agents/study/chat", json={"message": "shift my plan", "conversation_id": convo.id}
    )
    assert body.status_code == 200
    db.expire_all()
    row = db.get(Plan, plan["id"])
    assert row.steps[0].due_on == _today()
    patched = client.patch(f"/api/plans/{plan['id']}", json={"starts_on": "2026-12-01"}).json()
    assert patched["steps"][0]["due_on"] == "2026-12-01"


def test_the_agent_is_told_what_the_app_did_before_it_replies(client, db, monkeypatch):
    from app.llm.mock_provider import MockLLMProvider

    systems = []
    original = MockLLMProvider.stream_chat

    async def tracked(self, **kwargs):
        systems.append(kwargs["system"])
        async for delta in original(self, **kwargs):
            yield delta

    monkeypatch.setattr(MockLLMProvider, "stream_chat", tracked)
    _, convo, _ = _conversation_with_plan(db)
    client.post(
        "/api/agents/study/chat", json={"message": "save this plan", "conversation_id": convo.id}
    )
    assert 'Saved "3-day revision plan" as a checklist of 3 steps.' in systems[0]
    client.post(
        "/api/agents/study/chat", json={"message": "done with day 9", "conversation_id": convo.id}
    )
    assert "Do not say it was ticked off" in systems[1]


def test_events_and_checkins_fail_closed_like_facts():
    """No flag, or the model's flag, or the keyword list: any one withholds it."""
    today = date(2026, 9, 25)
    stub = Stub(
        {
            "facts": [],
            "events": [
                {"title": "Physio appointment", "date": "2026-09-28"},  # no flag
                {"title": "Mum's funeral", "date": "2026-09-29", "sensitive": False},
                {"title": "Team offsite", "date": "2026-09-30", "sensitive": True},
            ],
            "checkins": [
                {"agent": "fitness", "text": "ate 600 calories", "sensitive": False},
                {"agent": "fitness", "text": "ran 5k", "amount": 5, "unit": "km"},
            ],
        }
    )
    result = asyncio.run(
        analyze_turn(
            "I have a few things on", agent_id="modeer", provider=stub, model="stub", today=today
        )
    )
    assert [e.stored for e in result.events] == [False, False, False]
    assert [c.stored for c in result.checkins] == [False, False]
    assert "Never log food eaten, calories" in stub.systems[0]


def test_an_answer_about_a_followup_closes_it(client, db, monkeypatch):
    import app.agents.runtime as runtime_module
    from app.memory.llm_extraction import Outcome

    monkeypatch.setattr(settings, "memory_extraction", "llm")
    user = get_or_create_demo_user(db)
    user.timezone = "UTC"
    row = FollowUp(
        user_id=user.id,
        agent_id="career",
        title="Stripe interview",
        due_on=_today() - timedelta(days=1),
        asked_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    seen = {}

    async def fake(message, **kwargs):
        seen.update(kwargs)
        return TurnAnalysis(outcomes=[Outcome(row.id, row.title, "went well, second round")])

    monkeypatch.setattr(runtime_module, "analyze_turn", fake)
    body = client.post("/api/agents/career/chat", json={"message": "It went well!"}).json()
    assert [f.title for f in seen["asked"]] == ["Stripe interview"]
    assert body["followups_closed"][0]["title"] == "Stripe interview"
    db.expire_all()
    closed = db.get(FollowUp, row.id)
    assert closed.status == "done" and closed.outcome == "went well, second round"


def test_the_briefing_asks_how_it_went_only_until_the_agent_has():
    """Once asked in chat, the briefing stops asking; never every day for two weeks."""
    from types import SimpleNamespace

    item = SimpleNamespace(
        title="x", due_on=_today() - timedelta(days=1), asked_at=None, agent_id="career"
    )
    assert tracking._ask_in_briefing(item, _today())
    item.asked_at = datetime.now(UTC)
    assert not tracking._ask_in_briefing(item, _today())
    item.asked_at, item.due_on = None, _today() - timedelta(days=5)
    assert not tracking._ask_in_briefing(item, _today())


def test_a_handoff_needs_a_request_not_just_a_name():
    from app.memory.llm_extraction import named_teammates

    assert named_teammates("Tell Harvey about my interview", exclude="modeer") == {"career"}
    assert named_teammates("can you let Nova know I passed", exclude="modeer") == {"study"}
    assert named_teammates("pass this on to Emma", exclude="modeer") == {"finance"}
    assert named_teammates("قل لهارفي عن المقابلة", exclude="modeer") == {"career"}
    assert named_teammates("my friend Alex said hi", exclude="modeer") == set()
    assert named_teammates("I was born under Leo", exclude="study") == set()
    assert named_teammates("tell Harvey", exclude="career") == set()


def test_arabic_and_arabizi_messages_are_analysed_but_accents_are_not_enough():
    ask = {"agent_id": "study", "goals_allowed": False}
    assert worth_analyzing("ana 3andi interview bokra", **ask)
    assert worth_analyzing("je pars à Paris demain", **ask)
    assert not worth_analyzing("What is a café au lait?", **ask)
    assert worth_analyzing("Physics", previous_reply="ماذا تدرس؟", **ask)


def test_memory_work_does_not_hold_up_the_next_message(db, monkeypatch):
    """Once the reply is saved, the next message in the same conversation runs
    without waiting for the previous turn's memory analysis to finish."""
    import app.agents.runtime as runtime_module
    from app.agents.registry import require_agent
    from app.agents.runtime import AgentRuntime
    from app.db.session import SessionLocal
    from app.llm.mock_provider import MockLLMProvider

    monkeypatch.setattr(settings, "memory_extraction", "llm")
    gate = asyncio.Event()

    async def slow_analysis(message, **kwargs):
        if message.startswith("first"):
            await gate.wait()
        return TurnAnalysis()

    monkeypatch.setattr(runtime_module, "analyze_turn", slow_analysis)
    user = get_or_create_demo_user(db)
    convo = convo_service.create_conversation(db, user.id, "study")
    db.commit()
    cid, uid = convo.id, user.id

    async def two_messages():
        s1, s2 = SessionLocal(), SessionLocal()
        try:
            agent = require_agent("study")
            turn1 = AgentRuntime(provider=MockLLMProvider()).run_stream(
                s1, s1.get(User, uid), agent, s1.get(Conversation, cid), "first, I study law"
            )
            seen1 = []
            async for event in turn1:
                seen1.append(event.type)
                if event.type == "end":
                    break
            turn2 = AgentRuntime(provider=MockLLMProvider()).run_stream(
                s2, s2.get(User, uid), agent, s2.get(Conversation, cid), "second, I live in Rome"
            )
            seen2 = await asyncio.wait_for(_collect(turn2), timeout=5)
            gate.set()
            seen1 += [e.type async for e in turn1]
            return seen1, seen2
        finally:
            s1.close()
            s2.close()

    async def _collect(turn):
        return [e.type async for e in turn]

    seen1, seen2 = asyncio.run(two_messages())
    assert "end" in seen2 and "memory" in seen2, "the second message waited for the first"
    assert seen1[-1] == "memory"
