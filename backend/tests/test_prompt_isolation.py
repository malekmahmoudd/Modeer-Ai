"""What actually reaches the model, for real chat requests.

The memory tests prove the right rows come back from the database. That is not
the same claim as "one specialist's private notes never enter another
specialist's prompt", because the prompt is assembled several steps later —
and the function that decides what goes in it has changed before. So these
tests drive real HTTP requests through auth, budgeting and context building,
and read the provider's own input.

Each test carries a positive control: a prompt that SHOULD contain the marker
does. Without that, an assertion that a marker is absent passes just as well
when nothing is captured at all.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import AsyncIterator

import pytest

from app.core.config import settings
from app.llm import provider as provider_module
from app.llm.base import LLMMessage, LLMProvider

_ACTIVE = re.compile(r"^# ACTIVE AGENT:\s*(?P<name>[^\n—-]+)", re.M)


class RecordingProvider(LLMProvider):
    name = "recording"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def stream_chat(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        match = _ACTIVE.search(system)
        self.calls.append(
            {
                "agent": match.group("name").strip() if match else "(other)",
                "system": system,
                "messages": "\n".join(m.content for m in messages),
            }
        )
        yield "A short, useful reply."

    def prompt_for(self, agent_name: str) -> str:
        """Everything sent for one specialist's reply, system and messages together."""
        prompts = [
            c["system"] + "\n" + c["messages"] for c in self.calls if c["agent"] == agent_name
        ]
        assert prompts, f"no prompt was captured for {agent_name}"
        return "\n".join(prompts)

    def everything(self) -> str:
        return "\n".join(c["system"] + "\n" + c["messages"] for c in self.calls)


@pytest.fixture
def recorder(monkeypatch):
    recording = RecordingProvider()
    monkeypatch.setattr(provider_module, "_make_provider", lambda: recording)
    provider_module.get_llm_provider.cache_clear()
    # Several requests per test; the per-minute limit is not what is under test.
    monkeypatch.setattr(settings, "account_requests_per_minute", 1000)
    monkeypatch.setattr(settings, "account_daily_token_budget", 10_000_000)
    yield recording
    provider_module.get_llm_provider.cache_clear()


@pytest.fixture
def accounts(client, make_user, monkeypatch):
    alice, bob = make_user("Alice"), make_user("Bob")
    keys = {
        alice.id: hashlib.sha256(("a" * 40).encode()).hexdigest(),
        bob.id: hashlib.sha256(("b" * 40).encode()).hexdigest(),
    }
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(settings, "auth_access_keys", keys)
    origin = {"Origin": settings.frontend_url}

    def sign_in(key: str) -> None:
        client.cookies.clear()
        response = client.post("/api/auth/login", json={"access_key": key}, headers=origin)
        assert response.status_code == 200

    return sign_in, origin


def _chat(client, origin, agent: str, message: str, conversation_id: str | None = None) -> str:
    """Send one turn; return the conversation id so a follow-up can continue it.

    Without a conversation id every request starts a new conversation, so a
    second turn carries no history — which is what a first draft of the history
    test got wrong, and its positive control caught.
    """
    body = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = client.post(f"/api/agents/{agent}/chat", json=body, headers=origin)
    assert response.status_code == 200, response.text
    return response.json()["conversation_id"]


def _remember(client, origin, *, agent: str | None, key: str, value: str) -> None:
    if agent:
        body = {"agent_id": agent, "category": "weak_topics", "key": key, "value": value}
        response = client.post("/api/memory/agent", json=body, headers=origin)
    else:
        body = {"category": "career", "key": key, "value": value}
        response = client.post("/api/memory/shared", json=body, headers=origin)
    assert response.status_code == 201, response.text


def test_a_specialists_private_notes_never_reach_another_specialists_prompt(
    client, recorder, accounts
):
    sign_in, origin = accounts
    sign_in("a" * 40)
    _remember(client, origin, agent="study", key="weak_topic", value="STUDY-PRIVATE-MARKER")

    _chat(client, origin, "study", "What should I revise?")
    _chat(client, origin, "career", "What should my next job be?")

    # Positive control: the note Study owns is in Study's prompt.
    assert "STUDY-PRIVATE-MARKER" in recorder.prompt_for("Nova")
    # And nowhere near Career's.
    assert "STUDY-PRIVATE-MARKER" not in recorder.prompt_for("Harvey")


def test_one_accounts_data_never_reaches_another_accounts_prompt(client, recorder, accounts):
    sign_in, origin = accounts

    sign_in("b" * 40)
    _remember(client, origin, agent=None, key="employer", value="BOB-SHARED-MARKER")
    _remember(client, origin, agent="study", key="weak_topic", value="BOB-PRIVATE-MARKER")
    _chat(client, origin, "career", "BOB-MESSAGE-MARKER: help me with my CV")
    bob_calls = len(recorder.calls)

    sign_in("a" * 40)
    _chat(client, origin, "career", "What should my next job be?")
    _chat(client, origin, "study", "What should I revise?")

    # Positive control: Bob's shared fact did reach Bob's own prompt.
    assert "BOB-SHARED-MARKER" in "\n".join(c["system"] for c in recorder.calls[:bob_calls])
    alice_prompts = "\n".join(
        c["system"] + "\n" + c["messages"] for c in recorder.calls[bob_calls:]
    )
    for marker in ("BOB-SHARED-MARKER", "BOB-PRIVATE-MARKER", "BOB-MESSAGE-MARKER"):
        assert marker not in alice_prompts, f"{marker} crossed into another account's prompt"


def test_one_specialists_conversation_history_stays_in_its_own_prompt(client, recorder, accounts):
    sign_in, origin = accounts
    sign_in("a" * 40)
    study_convo = _chat(client, origin, "study", "STUDY-HISTORY-MARKER: my exam is thermodynamics")
    _chat(client, origin, "study", "And after that?", study_convo)
    _chat(client, origin, "career", "What should my next job be?")

    study_calls = [c for c in recorder.calls if c["agent"] == "Nova"]
    # Positive control: Study's second turn carried its own history.
    assert "STUDY-HISTORY-MARKER" in study_calls[-1]["messages"]
    assert "STUDY-HISTORY-MARKER" not in recorder.prompt_for("Harvey")


def test_ask_my_team_uses_no_private_notes_at_all(client, recorder, accounts, monkeypatch):
    """Every specialist's answer in a consult is handed to Modeer for the
    synthesis. A private note used in that answer would reach an agent the
    Memory page promises it never reaches — so a consult uses shared context only,
    and no call it makes may carry a private note."""
    monkeypatch.setattr(settings, "team_enabled", True)
    sign_in, origin = accounts
    sign_in("a" * 40)
    _remember(client, origin, agent="study", key="weak_topic", value="STUDY-PRIVATE-MARKER")
    _remember(client, origin, agent="career", key="weak_topic", value="CAREER-PRIVATE-MARKER")

    response = client.post(
        "/api/team/ask",
        json={"question": "What should I focus on?", "agent_ids": ["study", "career"]},
        headers=origin,
    )
    assert response.status_code == 200, response.text
    assert recorder.prompt_for("Nova") and recorder.prompt_for("Harvey")
    consult = recorder.everything()
    assert "STUDY-PRIVATE-MARKER" not in consult
    assert "CAREER-PRIVATE-MARKER" not in consult

    # Positive control: the same note does reach Study in an ordinary chat.
    _chat(client, origin, "study", "What should I revise?")
    assert "STUDY-PRIVATE-MARKER" in recorder.calls[-1]["system"]
