"""Suspension, handoff expiry, Leo's weekly review, structured check-ins, trips
with end dates, and relevance-ranked memory."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.agents import team
from app.agents.context import MEMORY_BLOCK_CHARS, build_context
from app.agents.registry import require_agent
from app.core.config import settings
from app.db.models import AgentMemory, CheckIn, FollowUp, Goal, User
from app.memory.llm_extraction import _details, _to_events
from app.tracking import service as tracking
from app.users.service import get_or_create_demo_user

TUESDAY = date(2026, 9, 29)


# --- suspension -------------------------------------------------------------------------


@pytest.fixture
def signed_in(client, db, monkeypatch):
    """An operator and a member, both with access keys, auth switched on."""
    operator = User(email="op@x.test", display_name="Op")
    member = User(email="m@x.test", display_name="Member")
    db.add_all([operator, member])
    db.commit()
    keys = {operator.id: "o" * 40, member.id: "m" * 40}
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(
        settings,
        "auth_access_keys",
        {uid: hashlib.sha256(key.encode()).hexdigest() for uid, key in keys.items()},
    )
    monkeypatch.setattr(settings, "admin_accounts", [operator.id])
    return operator, member, keys


ORIGIN = {"Origin": "http://localhost:3000"}


def _post(client, path):
    return client.post(path, headers={"Origin": settings.frontend_url})


def _login(client, key):
    client.cookies.clear()
    return client.post(
        "/api/auth/login", json={"access_key": key}, headers={"Origin": settings.frontend_url}
    )


def test_an_operator_can_suspend_and_restore_an_account(client, db, signed_in):
    operator, member, keys = signed_in
    assert _login(client, keys[member.id]).status_code == 200
    assert client.get("/api/users/me").status_code == 200

    _login(client, keys[operator.id])
    assert _post(client, f"/api/admin/accounts/{member.id}/suspend").json()["suspended"] is True
    assert _post(client, f"/api/admin/accounts/{operator.id}/suspend").status_code == 400

    login = _login(client, keys[member.id])
    assert login.status_code == 403 and "suspended" in login.json()["detail"]

    _login(client, keys[operator.id])
    _post(client, f"/api/admin/accounts/{member.id}/unsuspend")
    assert _login(client, keys[member.id]).status_code == 200
    assert client.get("/api/users/me").status_code == 200


def test_a_suspended_session_stops_working_everywhere(client, db, signed_in):
    _, member, keys = signed_in
    _login(client, keys[member.id])
    row = db.get(User, member.id)
    row.suspended_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    assert client.get("/api/users/me").status_code == 403
    chat = client.post("/api/agents/study/chat/stream", json={"message": "hello"}, headers=ORIGIN)
    assert chat.status_code == 403


def test_only_operators_can_suspend(client, db, signed_in):
    _, member, keys = signed_in
    _login(client, keys[member.id])
    assert _post(client, f"/api/admin/accounts/{member.id}/suspend").status_code == 404


# --- handoff notes --------------------------------------------------------------------------


def test_a_note_is_marked_seen_when_its_teammate_replies(client, db):
    user = get_or_create_demo_user(db)
    note = AgentMemory(
        user_id=user.id,
        agent_id="career",
        scope="agent",
        category="handoff",
        key="from_modeer",
        value="Stripe interview prep",
        source="modeer",
    )
    db.add(note)
    db.commit()
    client.post("/api/agents/career/chat", json={"message": "hi"})
    db.expire_all()
    assert db.get(AgentMemory, note.id).seen_at is not None
    lines = team.recent_activity(
        db, user.id, exclude_conversation="x", now=datetime.now().astimezone()
    )
    assert any("picked up" in line for line in lines)


def test_notes_expire_after_being_seen_or_going_stale(db):
    user = get_or_create_demo_user(db)
    now = datetime.now(UTC)
    old_seen = AgentMemory(
        user_id=user.id,
        agent_id="career",
        scope="agent",
        category="handoff",
        key="from_modeer",
        value="a",
        source="modeer",
        seen_at=(now - timedelta(days=15)).replace(tzinfo=None),
    )
    fresh = AgentMemory(
        user_id=user.id,
        agent_id="study",
        scope="agent",
        category="handoff",
        key="from_modeer",
        value="b",
        source="modeer",
    )
    stale = AgentMemory(
        user_id=user.id,
        agent_id="travel",
        scope="agent",
        category="handoff",
        key="from_modeer",
        value="c",
        source="modeer",
        created_at=now - timedelta(days=31),
    )
    db.add_all([old_seen, fresh, stale])
    db.commit()
    team.expire_handoffs(db, user.id, now=now)
    db.commit()
    left = [n.value for n in db.scalars(select(AgentMemory))]
    assert left == ["b"]


# --- Leo's weekly review ----------------------------------------------------------------------


def test_the_week_adds_up_spending_in_code_and_flags_quiet_goals(db):
    user = get_or_create_demo_user(db)
    db.add_all(
        [
            CheckIn(
                user_id=user.id,
                agent_id="finance",
                text="groceries",
                amount=40.5,
                details={"direction": "out", "currency": "EGP"},
                logged_on=TUESDAY,
            ),
            CheckIn(
                user_id=user.id,
                agent_id="finance",
                text="rent",
                amount=9000,
                details={"direction": "out", "currency": "EGP"},
                logged_on=TUESDAY,
            ),
            CheckIn(
                user_id=user.id,
                agent_id="finance",
                text="salary",
                amount=20000,
                details={"direction": "in", "currency": "EGP"},
                logged_on=TUESDAY,
            ),
            CheckIn(user_id=user.id, agent_id="fitness", text="ran 5k", logged_on=TUESDAY),
            Goal(
                user_id=user.id,
                title="Learn Spanish",
                updated_at=datetime.now(UTC) - timedelta(days=40),
            ),
        ]
    )
    db.commit()
    review = tracking.weekly_review(db, user.id, today=TUESDAY + timedelta(days=1))
    assert review["spending"] == {"EGP": 9040.5}
    assert "spent 9,040.50 EGP" in review["summary"]
    assert review["quiet_goals"] == ["Learn Spanish"]


def test_leo_gets_the_week_only_when_asked(db):
    user = get_or_create_demo_user(db)
    asked = tracking.review_section(db, user.id, today=TUESDAY, message="How was my week?")
    assert asked.startswith("## The past week and the next")
    assert tracking.review_section(db, user.id, today=TUESDAY, message="Write me a haiku") == ""
    monday = TUESDAY - timedelta(days=1)
    assert tracking.review_section(db, user.id, today=monday, message="hi")


# --- structured check-ins and progression --------------------------------------------------------


def test_checkin_details_are_validated_field_by_field():
    assert _details(
        {"exercise": "Squat", "sets": 3, "reps": 5, "load": 80, "load_unit": "kg", "rpe": 8}
    ) == {"exercise": "Squat", "sets": 3, "reps": 5, "load": 80, "load_unit": "kg", "rpe": 8}
    assert _details({"sets": 900, "load": -5, "rpe": 11}) is None
    assert _details({"direction": "out", "currency": "EGP"}) == {
        "direction": "out",
        "currency": "EGP",
    }
    assert _details({"direction": "sideways", "currency": "dollars please"}) is None
    assert _details("3x5") is None


def test_maddie_sees_progression_from_her_logs(db):
    user = get_or_create_demo_user(db)
    for i, load in enumerate([70, 75, 80]):
        db.add(
            CheckIn(
                user_id=user.id,
                agent_id="fitness",
                text="squats",
                details={
                    "exercise": "Squat",
                    "sets": 3,
                    "reps": 5,
                    "load": load,
                    "load_unit": "kg",
                },
                logged_on=TUESDAY - timedelta(days=14 - i * 7),
            )
        )
    db.commit()
    sections, _ = tracking.context_sections(
        db, user.id, agent_id="fitness", is_leo=False, today=TUESDAY
    )
    text = "\n".join(sections)
    assert "## Progression from their logs" in text
    assert "squat: last" in text and "3×5 @ 80 kg" in text and "best 80 kg" in text


# --- trips with an end date ---------------------------------------------------------------------


def test_a_trip_is_asked_about_after_it_ends_not_while_it_runs(db):
    user = get_or_create_demo_user(db)
    trip = FollowUp(
        user_id=user.id,
        agent_id="travel",
        title="Istanbul trip",
        due_on=TUESDAY - timedelta(days=2),
        ends_on=TUESDAY + timedelta(days=2),
    )
    db.add(trip)
    db.commit()
    during, ask = tracking.context_sections(
        db, user.id, agent_id="travel", is_leo=False, today=TUESDAY
    )
    assert ask == [] and "happening now" in "\n".join(during)
    after, ask = tracking.context_sections(
        db, user.id, agent_id="travel", is_leo=False, today=TUESDAY + timedelta(days=3)
    )
    assert ask == [trip.id]


def test_event_end_dates_are_read_and_bounded():
    today = date(2026, 9, 25)
    events = _to_events(
        [
            {
                "title": "Istanbul trip",
                "date": "2026-11-10",
                "end_date": "2026-11-14",
                "sensitive": False,
            },
            {
                "title": "Odd dates",
                "date": "2026-11-10",
                "end_date": "2026-11-01",
                "sensitive": False,
            },
        ],
        agent_id="travel",
        today=today,
    )
    assert events[0].ends_on == date(2026, 11, 14)
    assert events[1].ends_on is None  # ends before it starts: ignored


def test_the_followups_api_takes_an_end_date(client):
    made = client.post(
        "/api/followups",
        json={
            "title": "Trip",
            "due_on": "2027-01-10",
            "ends_on": "2027-01-14",
            "agent_id": "travel",
        },
    )
    assert made.json()["ends_on"] == "2027-01-14"
    bad = client.post(
        "/api/followups", json={"title": "Trip", "due_on": "2027-01-10", "ends_on": "2027-01-01"}
    )
    assert bad.status_code == 422


# --- memory ranking ----------------------------------------------------------------------


def test_past_the_ceiling_the_relevant_fact_survives():
    now = datetime.now(UTC)
    filler = [
        SimpleNamespace(
            category="career",
            key=f"a_note_{i}",
            value="x" * 900,
            pinned=False,
            updated_at=now - timedelta(days=1),
        )
        for i in range(10)
    ]
    relevant = SimpleNamespace(
        category="career",
        key="zz_interview",
        value="Stripe final round",
        pinned=False,
        updated_at=now - timedelta(days=90),
    )
    packet = build_context(
        agent=require_agent("career"),
        user=SimpleNamespace(display_name="S", profile={}, onboarded=True, id="u"),
        shared=[*filler, relevant],
        agent_memory=[],
        goals=[],
        history=[],
        user_message="How should I prepare for the Stripe final round?",
    )
    block = packet.system.split("<<PERSONAL_CONTEXT>>")[1].split("<</PERSONAL_CONTEXT>>")[0]
    assert "Stripe final round" in block
    assert len(block) <= MEMORY_BLOCK_CHARS + 200
