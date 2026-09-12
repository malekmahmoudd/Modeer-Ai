"""Regressions for the defects found in the 2026-09-11 production-readiness review.

Each test names the behaviour that was wrong, so a later change that brings it
back fails here rather than in someone's account.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest
from sqlalchemy import func, select

from app.agents import runtime as runtime_module
from app.agents.context import MEMORY_BLOCK_CHARS, build_context
from app.agents.registry import require_agent
from app.agents.runtime import AgentRuntime
from app.conversations import service as convo_service
from app.core.config import settings
from app.db.models import Conversation, Message, SharedMemory
from app.llm import provider as provider_module
from app.llm.base import LLMProvider
from app.memory import service as memory_service
from app.memory.extraction import Candidate, extract_candidates


class Fixed(LLMProvider):
    name = "fixed"

    def __init__(self, reply="A reply.", gate=None):
        self.reply, self.gate, self.calls = reply, gate, 0

    async def stream_chat(self, *, system, messages, model, temperature, max_tokens):
        self.calls += 1
        if self.gate is not None and "# ACTIVE AGENT:" in system:
            await self.gate.wait()
        yield self.reply if "# ACTIVE AGENT:" in system else "[]"


@pytest.fixture
def provider(monkeypatch):
    chosen = Fixed()
    monkeypatch.setattr(provider_module, "_make_provider", lambda: chosen)
    provider_module.get_llm_provider.cache_clear()
    monkeypatch.setattr(settings, "memory_extraction", "rules")
    yield chosen
    provider_module.get_llm_provider.cache_clear()


# --- RR-01: a correction made by hand is the user's, and stays -------------------------


def test_a_corrected_memory_is_not_overwritten_by_later_extraction(client, db, user, provider):
    """The Memory page edits with PATCH. Before this fix the row kept the
    extracting agent as its source, so the next mention overwrote the person."""
    memory_service.apply_candidates(
        db,
        user.id,
        [Candidate("shared", None, "context", "location", "Cairo", 0.9, False, True, "")],
        source="modeer",
    )
    db.commit()
    row_id = db.scalar(select(SharedMemory.id).where(SharedMemory.user_id == user.id))

    assert client.patch(f"/api/memory/shared/{row_id}", json={"value": "Giza"}).status_code == 200
    db.expire_all()
    assert db.get(SharedMemory, row_id).source == "user"

    client.post("/api/agents/modeer/chat", json={"message": "By the way I live in Alexandria now."})
    db.expire_all()
    assert db.get(SharedMemory, row_id).value == "Giza"


def test_pinning_a_fact_does_not_freeze_it(client, db, user, provider):
    """Marking a fact as content the person wrote is about the wording. Pinning
    says "keep this in view", not "this is my sentence now", so an automatic
    update must still be allowed — and the pin must survive it."""
    memory_service.apply_candidates(
        db,
        user.id,
        [Candidate("shared", None, "context", "location", "Cairo", 0.9, False, True, "")],
        source="modeer",
    )
    db.commit()
    row_id = db.scalar(select(SharedMemory.id).where(SharedMemory.user_id == user.id))

    assert client.patch(f"/api/memory/shared/{row_id}", json={"pinned": True}).status_code == 200
    db.expire_all()
    assert db.get(SharedMemory, row_id).source == "modeer"

    client.post("/api/agents/modeer/chat", json={"message": "I live in Alexandria now."})
    db.expire_all()
    row = db.get(SharedMemory, row_id)
    assert (row.value, row.pinned) == ("Alexandria", True)


def test_positive_control_extraction_still_updates_its_own_facts(client, db, user, provider):
    memory_service.apply_candidates(
        db,
        user.id,
        [Candidate("shared", None, "context", "location", "Cairo", 0.9, False, True, "")],
        source="modeer",
    )
    db.commit()
    client.post("/api/agents/modeer/chat", json={"message": "By the way I live in Alexandria now."})
    db.expire_all()
    value = db.scalar(select(SharedMemory.value).where(SharedMemory.user_id == user.id))
    assert value == "Alexandria", "the rules extractor kept a trailing word (RR-11)"


# --- RR-03: a duplicate label is answered, not crashed into an alert -------------------


def test_renaming_a_label_onto_an_existing_one_is_refused_not_a_server_error(client, user):
    first = client.post("/api/memory/shared", json={"key": "alpha", "value": "one"}).json()
    client.post("/api/memory/shared", json={"key": "beta", "value": "two"})

    clash = client.patch(f"/api/memory/shared/{first['id']}", json={"key": "beta"})
    assert clash.status_code == 409
    assert "label" in clash.json()["detail"]

    assert client.get("/api/memory/shared").status_code == 200
    blank = client.patch(f"/api/memory/shared/{first['id']}", json={"key": "   "})
    renamed = client.patch(f"/api/memory/shared/{first['id']}", json={"key": "gamma"})
    assert (blank.status_code, renamed.status_code) == (422, 200)


def test_a_stored_fact_has_a_size_limit(client, user):
    too_big = client.post("/api/memory/shared", json={"key": "notes", "value": "x" * 5000})
    assert too_big.status_code == 422
    ok = client.post("/api/memory/shared", json={"key": "notes", "value": "x" * 500})
    assert ok.status_code == 201


def test_the_memory_block_in_a_prompt_has_a_ceiling(db, user):
    rows = [
        SharedMemory(
            user_id=user.id,
            scope="shared",
            category="preferences",
            key=f"note_{i}",
            value="y" * 1900,
            source="user",
            confidence=1.0,
            sensitive=False,
        )
        for i in range(10)
    ]
    db.add_all(rows)
    db.commit()

    packet = build_context(
        agent=require_agent("modeer"),
        user=user,
        shared=rows,
        agent_memory=[],
        goals=[],
        history=[],
        user_message="hello",
    )
    block = packet.system.split("<<PERSONAL_CONTEXT>>")[1].split("<</PERSONAL_CONTEXT>>")[0]
    assert "more not shown here" in block
    assert len(block) <= MEMORY_BLOCK_CHARS + 200
    assert packet.diagnostics["personal_context_count"] < len(rows)


# --- RR-04: a revoked session is told to sign in ---------------------------------------


def _sign_in(client, monkeypatch, account, key="a" * 40):
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(
        settings, "auth_access_keys", {account.id: hashlib.sha256(key.encode()).hexdigest()}
    )
    origin = {"Origin": settings.frontend_url}
    login = client.post("/api/auth/login", json={"access_key": key}, headers=origin)
    assert login.status_code == 200
    return origin


def test_a_revoked_session_gets_401_from_the_chat_stream(
    client, db, make_user, monkeypatch, provider
):
    alice = make_user("Alice")
    origin = _sign_in(client, monkeypatch, alice)
    working = client.post(
        "/api/agents/study/chat/stream", json={"message": "hello there"}, headers=origin
    )
    assert working.status_code == 200, "positive control: a live session streams"

    alice.session_epoch = (alice.session_epoch or 0) + 1  # "sign out every device" elsewhere
    db.commit()

    revoked = client.post(
        "/api/agents/study/chat/stream", json={"message": "hello there"}, headers=origin
    )
    assert revoked.status_code == 401
    assert "sign in" in revoked.json()["detail"].lower()


def test_another_accounts_conversation_is_refused_before_the_stream(
    client, make_user, monkeypatch, provider
):
    alice, bob = make_user("Alice"), make_user("Bob")
    origin = _sign_in(client, monkeypatch, alice)
    convo = client.post("/api/conversations", json={"agent_id": "study"}, headers=origin).json()
    monkeypatch.setattr(
        settings, "auth_access_keys", {bob.id: hashlib.sha256(("b" * 40).encode()).hexdigest()}
    )
    client.cookies.clear()
    client.post("/api/auth/login", json={"access_key": "b" * 40}, headers=origin)

    stolen = client.post(
        "/api/agents/study/chat/stream",
        json={"message": "hello there", "conversation_id": convo["id"]},
        headers=origin,
    )
    assert stolen.status_code == 404


# --- RR-05: two retries of one turn do not both answer ---------------------------------


def test_a_second_retry_arriving_mid_stream_is_refused(db, user, monkeypatch):
    convo = convo_service.create_conversation(db, user.id, "study")
    convo_service.add_message(db, convo, "user", "Explain contract law.")
    convo_service.add_message(db, convo, "assistant", "", {"completion": "failed"})
    db.commit()
    cid = convo.id
    monkeypatch.setattr(settings, "memory_extraction", "rules")

    async def two_retries():
        from app.db.session import SessionLocal

        gate = asyncio.Event()
        shared = Fixed(reply="The whole answer.", gate=gate)
        s1, s2 = SessionLocal(), SessionLocal()
        try:
            turn1 = AgentRuntime(provider=shared).run_stream(
                s1,
                s1.get(type(user), user.id),
                require_agent("study"),
                s1.get(Conversation, cid),
                None,
                retry=True,
            )
            first = await turn1.__anext__()
            turn2 = AgentRuntime(provider=shared).run_stream(
                s2,
                s2.get(type(user), user.id),
                require_agent("study"),
                s2.get(Conversation, cid),
                None,
                retry=True,
            )
            second = asyncio.ensure_future(turn2.__anext__())
            await asyncio.sleep(0.05)
            assert not second.done(), "the second retry did not wait for the first"
            gate.set()
            rest1 = [e async for e in turn1]
            event2 = await second
            rest2 = [e async for e in turn2]
            return first.type, [e.type for e in rest1], event2, [e.type for e in rest2]
        finally:
            s1.close()
            s2.close()

    first, rest1, event2, _ = asyncio.run(two_retries())
    assert first == "start" and "end" in rest1
    assert event2.type == "error" and event2.data["status"] == 409

    db.expire_all()
    replies = db.scalars(
        select(Message).where(Message.conversation_id == cid, Message.role == "assistant")
    ).all()
    assert [(m.content, m.meta.get("completion")) for m in replies] == [
        ("The whole answer.", "completed")
    ]
    assert (
        db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == cid, Message.role == "user")
        )
        == 1
    )


def test_the_turn_lock_is_released_and_forgotten(db, user, provider, client):
    client.post("/api/agents/study/chat", json={"message": "hello there"})
    assert runtime_module._turn_locks == {}, "a lock was left behind after the turn"


# --- RR-06: memory trouble is not reported as a failed reply ---------------------------


def test_a_memory_failure_after_the_reply_is_reported_as_a_memory_failure(
    client, user, provider, monkeypatch
):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated database trouble")

    monkeypatch.setattr(memory_service, "apply_candidates", boom)
    response = client.post("/api/agents/study/chat/stream", json={"message": "I live in Cairo."})
    events = [
        line[len("data: ") :] for line in response.text.splitlines() if line.startswith("data: ")
    ]
    import json as _json

    parsed = [_json.loads(e) for e in events]
    kinds = [e["type"] for e in parsed]
    assert kinds[-1] == "memory", f"the reply was reported as failed: {kinds}"
    assert "memory could not be updated" in parsed[-1]["error"]
    assert "error" not in kinds


# --- RR-11: trailing words are not part of the fact ------------------------------------


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("I live in Alexandria now.", "Alexandria"),
        ("I live in Alexandria currently", "Alexandria"),
        ("I live in Alexandria", "Alexandria"),
    ],
)
def test_extraction_drops_trailing_filler(message, expected):
    found = [c for c in extract_candidates(message, agent_id="modeer") if c.key == "location"]
    assert [c.value for c in found] == [expected]


# --- logs name the route, never an id ---------------------------------------------------


def test_access_log_names_the_full_route_without_ids(client, user, db):
    """FastAPI 0.141 keeps included routers nested, so the route's own path lost
    the /api prefix. The template is what operators grep; ids must stay out."""
    from app.core.observability import _route_template

    convo = convo_service.create_conversation(db, user.id, "study")
    db.commit()
    seen = {}

    original = _route_template
    import app.core.observability as obs

    obs._route_template = lambda request: seen.setdefault(request.url.path, original(request))
    try:
        client.get(f"/api/conversations/{convo.id}")
        client.get("/api/memory/shared")
    finally:
        obs._route_template = original

    assert seen[f"/api/conversations/{convo.id}"] == "/api/conversations/{conversation_id}"
    assert seen["/api/memory/shared"] == "/api/memory/shared"
    assert convo.id not in " ".join(seen.values())


# --- messages keep the order they were written in --------------------------------------


def test_messages_written_in_the_same_clock_tick_keep_their_order(db, user):
    """A clock need not tick between two writes — on Windows it moves in ~15ms
    steps. Ordering fell back to a random id, so a reply could sort before the
    question it answered, in the transcript and in what the model was sent."""
    convo = convo_service.create_conversation(db, user.id, "study")
    written = []
    for i in range(12):
        written.append(convo_service.add_message(db, convo, "user", f"q{i}").id)
        written.append(convo_service.add_message(db, convo, "assistant", f"a{i}").id)
    db.commit()

    assert [m.id for m in convo_service.history(db, convo.id)] == written
    db.expire_all()
    reloaded = convo_service.get_conversation(db, user.id, convo.id)
    assert [m.content for m in reloaded.messages] == [f"{r}{i}" for i in range(12) for r in "qa"]
