"""How a reply ended is saved, streamed and reloaded — and retry is safe.

The provider tests prove the provider reports truncated and interrupted streams.
These prove the rest of the path: the runtime keeps the text that arrived, saves
the state beside it, streams it to the client, and a history reload shows the
same thing. A retry regenerates the unfinished turn in place — never a second
copy of the user's message, never a provider call nobody asked for.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select

from app.agents.registry import require_agent
from app.agents.runtime import AgentRuntime
from app.conversations import service as convo_service
from app.core.config import settings
from app.db.models import Conversation, Message, UsageBucket
from app.llm import provider as provider_module
from app.llm.base import INTERRUPTED, TRUNCATED, LLMMessage, LLMProvider, StreamEnded
from app.llm.openai_compat_provider import ProviderError

CUT = "This reply reached its length limit and may be incomplete."
DROPPED = "The connection to the AI provider dropped before this reply finished."


class ScriptedProvider(LLMProvider):
    """Plays one script per call: strings are streamed, exceptions are raised."""

    name = "scripted"

    def __init__(self) -> None:
        self.scripts: list[list] = []
        self.calls: list[list[LLMMessage]] = []

    def then(self, *steps) -> ScriptedProvider:
        self.scripts.append(list(steps))
        return self

    async def stream_chat(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        self.calls.append(list(messages))
        assert self.scripts, "the provider was called more times than the test expected"
        for step in self.scripts.pop(0):
            if isinstance(step, BaseException):
                raise step
            yield step


@pytest.fixture
def scripted(monkeypatch):
    provider = ScriptedProvider()
    monkeypatch.setattr(provider_module, "_make_provider", lambda: provider)
    provider_module.get_llm_provider.cache_clear()
    monkeypatch.setattr(settings, "memory_extraction", "rules")
    yield provider
    provider_module.get_llm_provider.cache_clear()


def _stream(client, body: dict, agent: str = "study") -> list[dict]:
    response = client.post(f"/api/agents/{agent}/chat/stream", json=body)
    assert response.status_code == 200, response.text
    return [
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def _one(events: list[dict], kind: str) -> dict:
    found = [e for e in events if e["type"] == kind]
    assert len(found) == 1, (kind, events)
    return found[0]


def _messages(client, conversation_id: str) -> list[dict]:
    response = client.get(f"/api/conversations/{conversation_id}")
    assert response.status_code == 200, response.text
    return response.json()["messages"]


# --- each completion state, live and on reload -------------------------------


def test_completed_reply_streams_and_reloads_as_completed(client, scripted):
    scripted.then("Hello ", "there.")
    events = _stream(client, {"message": "Hi, I study law."})

    end = _one(events, "end")
    assert (end["content"], end["completion"], end["notice"]) == ("Hello there.", "completed", "")
    reply = _messages(client, end["conversation_id"])[-1]
    assert (reply["content"], reply["completion"]) == ("Hello there.", "completed")


@pytest.mark.parametrize(
    ("status", "notice"),
    [(TRUNCATED, CUT), (INTERRUPTED, DROPPED)],
    ids=["truncated", "interrupted"],
)
def test_partial_reply_keeps_its_text_and_says_how_it_ended(client, scripted, status, notice):
    scripted.then("The first half ", "of an answer.", StreamEnded(status, notice))
    events = _stream(client, {"message": "Explain contract law."})

    assert [e["text"] for e in events if e["type"] == "delta"] == [
        "The first half ",
        "of an answer.",
    ]
    end = _one(events, "end")
    assert end["content"] == "The first half of an answer."
    assert (end["completion"], end["notice"]) == (status, notice)
    assert not [e for e in events if e["type"] == "error"]

    reply = _messages(client, end["conversation_id"])[-1]
    assert reply["content"] == "The first half of an answer."
    assert reply["completion"] == status
    assert reply["meta"]["notice"] == notice


def test_failed_reply_is_recorded_as_failed_not_as_an_answer(client, scripted):
    scripted.then(ProviderError("The AI provider could not respond (HTTP 503)."))
    events = _stream(client, {"message": "Explain contract law."})

    assert not [e for e in events if e["type"] in ("end", "delta")]
    error = _one(events, "error")
    assert error["completion"] == "failed"
    assert error["status"] == 502
    assert "could not respond" in error["error"]

    roles = [
        (m["role"], m["content"], m["completion"])
        for m in _messages(client, error["conversation_id"])
    ]
    assert roles == [("user", "Explain contract law.", "completed"), ("assistant", "", "failed")]
    assert error["message_id"] == _messages(client, error["conversation_id"])[-1]["id"]


def test_empty_reply_is_a_failure_not_a_placeholder_answer(client, scripted):
    scripted.then("   ", "\n")
    events = _stream(client, {"message": "Explain contract law."})

    error = _one(events, "error")
    assert "empty" in error["error"]
    reply = _messages(client, error["conversation_id"])[-1]
    assert (reply["content"], reply["completion"]) == ("", "failed")
    assert "(no response)" not in json.dumps(events)


def test_sync_endpoint_reports_how_the_reply_ended(client, scripted):
    scripted.then("Cut short", StreamEnded(TRUNCATED, CUT))
    response = client.post("/api/agents/study/chat", json={"message": "Explain contract law."})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["content"], body["completion"], body["notice"]) == ("Cut short", TRUNCATED, CUT)


def test_a_failed_turn_is_left_out_of_the_next_prompt(client, scripted):
    scripted.then(ProviderError("The AI provider could not respond (HTTP 503)."))
    scripted.then("A real answer.")
    first = _one(_stream(client, {"message": "First question."}), "error")
    _stream(client, {"message": "Second question.", "conversation_id": first["conversation_id"]})

    sent = scripted.calls[-1]
    assert [m.content for m in sent if m.role == "user"][-2:] == [
        "First question.",
        "Second question.",
    ], "positive control: the earlier turn is in the history"
    assert all(m.content.strip() for m in sent), "an empty failed reply reached the model"


def test_a_partial_reply_stays_in_the_next_prompt(client, scripted):
    """Truncated text is real context: what the person read, the model sees."""
    scripted.then("Half an answer", StreamEnded(TRUNCATED, CUT))
    scripted.then("Continuing.")
    end = _one(_stream(client, {"message": "First question."}), "end")
    _stream(client, {"message": "Go on.", "conversation_id": end["conversation_id"]})

    assert any(m.role == "assistant" and m.content == "Half an answer" for m in scripted.calls[-1])


# --- retry --------------------------------------------------------------------


@pytest.mark.parametrize(
    "first",
    [
        [ProviderError("The AI provider could not respond (HTTP 503).")],
        ["Half an answer", StreamEnded(TRUNCATED, CUT)],
        ["Half an answer", StreamEnded(INTERRUPTED, DROPPED)],
    ],
    ids=["failed", "truncated", "interrupted"],
)
def test_retry_regenerates_the_unfinished_turn_in_place(client, scripted, first):
    scripted.then(*first)
    scripted.then("The whole answer.")
    events = _stream(client, {"message": "Explain contract law."})
    convo = events[0]["conversation_id"]

    retried = _stream(client, {"conversation_id": convo, "retry": True})
    end = _one(retried, "end")
    assert (end["content"], end["completion"]) == ("The whole answer.", "completed")

    history = [(m["role"], m["content"], m["completion"]) for m in _messages(client, convo)]
    assert history == [
        ("user", "Explain contract law.", "completed"),
        ("assistant", "The whole answer.", "completed"),
    ], "a retry duplicated or left behind a message"
    # The retry asked about the original message, with no stale partial beside it.
    assert [m.content for m in scripted.calls[-1]][-1] == "Explain contract law."
    assert not any(m.role == "assistant" for m in scripted.calls[-1])


def test_retry_is_refused_once_the_latest_reply_completed(client, scripted, db):
    scripted.then("Done.")
    convo = _one(_stream(client, {"message": "Explain contract law."}), "end")["conversation_id"]
    before = _messages(client, convo)

    error = _one(_stream(client, {"conversation_id": convo, "retry": True}), "error")
    assert error["status"] == 409
    sync = client.post("/api/agents/study/chat", json={"conversation_id": convo, "retry": True})
    assert sync.status_code == 409

    assert len(scripted.calls) == 1, "a refused retry still called the provider"
    assert _messages(client, convo) == before


def test_retry_does_not_learn_from_the_same_message_twice(client, scripted, monkeypatch):
    """Extraction is a provider call too. A retry of a turn that already got
    partway has already extracted from this message, so it must not pay again."""
    monkeypatch.setattr(settings, "memory_extraction", "llm")
    scripted.then("Half an answer", StreamEnded(INTERRUPTED, DROPPED))
    scripted.then("[]")  # the extraction call for the first attempt
    scripted.then("The whole answer.")  # the retry; no extraction script follows
    convo = _stream(client, {"message": "I study law at Cairo University."})[0]["conversation_id"]

    _one(_stream(client, {"conversation_id": convo, "retry": True}), "end")
    assert len(scripted.calls) == 3


def test_a_turn_with_no_reply_at_all_can_be_retried(client, scripted, db, user):
    """The client left before the first word: only the user message was saved."""
    convo = convo_service.create_conversation(db, user.id, "study")
    convo_service.add_message(db, convo, "user", "Explain contract law.")
    db.commit()
    scripted.then("The whole answer.")

    end = _one(_stream(client, {"conversation_id": convo.id, "retry": True}), "end")
    assert end["completion"] == "completed"
    assert [m["role"] for m in _messages(client, convo.id)] == ["user", "assistant"]


# --- the client going away ---------------------------------------------------


def _turn(db, user, provider):
    convo = convo_service.create_conversation(db, user.id, "study")
    db.commit()
    runtime = AgentRuntime(provider=provider)
    return convo, runtime.run_stream(db, user, require_agent("study"), convo, "Explain it.")


@pytest.mark.parametrize(
    ("steps", "expected"),
    [(["The first words"], ("The first words", "interrupted")), ([], ("", "failed"))],
    ids=["after-text", "before-text"],
)
def test_client_leaving_mid_reply_saves_what_arrived(db, user, steps, expected):
    class Stalls(ScriptedProvider):
        async def stream_chat(self, **kwargs):
            for step in steps:
                yield step
            await asyncio.sleep(3600)  # a reply that never finishes
            yield "never"

    async def scenario():
        convo, turn = _turn(db, user, Stalls())
        task = asyncio.ensure_future(_drain(turn))
        await asyncio.sleep(0.05)
        task.cancel()  # what the server does when the browser goes away
        with pytest.raises(asyncio.CancelledError):
            await task
        return convo

    async def _drain(turn):
        async for _ in turn:
            pass

    convo = asyncio.run(scenario())
    db.expire_all()
    reply = convo_service.history(db, convo.id)[-1]
    assert (reply.role, reply.content, reply.meta["completion"]) == ("assistant", *expected)
    assert "connection closed" in reply.meta["notice"]


# --- blank messages ------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/agents/study/chat/stream", "/api/agents/study/chat"])
@pytest.mark.parametrize(
    "body",
    [
        {"message": ""},
        {"message": "   "},
        {"message": " \n\t "},
        {},
        {"retry": True},
        {"retry": True, "conversation_id": "x", "message": "a new message"},
    ],
    ids=[
        "empty",
        "spaces",
        "whitespace",
        "missing",
        "retry-without-conversation",
        "retry-with-text",
    ],
)
def test_invalid_turns_are_refused_before_any_work(client, scripted, db, path, body):
    response = client.post(path, json=body)
    assert response.status_code == 422, response.text

    assert scripted.calls == [], "the provider was called"
    assert _count(db, Conversation) == 0
    assert _count(db, Message) == 0
    assert _tokens_charged(db) == 0, "token quota was charged"


def test_positive_control_a_real_turn_does_all_of_that(client, scripted, db):
    """Without this, the zeros above would pass just as well if nothing counted."""
    scripted.then("An answer.")
    _one(_stream(client, {"message": "Explain contract law."}), "end")
    assert len(scripted.calls) == 1
    assert _count(db, Conversation) == 1
    assert _count(db, Message) == 2
    assert _tokens_charged(db) > 0


def _count(db, model) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


def _tokens_charged(db) -> int:
    # Request counting still sees a malformed request — that is rate limiting
    # doing its job. Provider work is charged in the "tokens" bucket.
    db.expire_all()
    return db.scalar(
        select(func.coalesce(func.sum(UsageBucket.amount), 0)).where(UsageBucket.kind == "tokens")
    )


def test_blank_team_question_is_refused(client, scripted):
    response = client.post("/api/team/ask", json={"question": "  ", "agent_ids": ["study"]})
    assert response.status_code == 422
    assert scripted.calls == []
