import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.usage import BudgetExceeded, account_scope, charge
from app.db.models import UsageBucket
from app.db.session import SessionLocal
from tests.test_auth import enable


def test_atomic_limit_and_reset(monkeypatch):
    monkeypatch.setattr("app.core.usage.time.time", lambda: 120)

    def attempt(_):
        try:
            charge("alice", "requests", 1, 3, 60)
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(8))) == 3
    charge("bob", "requests", 1, 3, 60)
    monkeypatch.setattr("app.core.usage.time.time", lambda: 180)
    charge("alice", "requests", 1, 3, 60)


def test_daily_atomic_budget_and_rollover(monkeypatch):
    monkeypatch.setattr("app.core.usage.time.time", lambda: 86401)
    charge("alice", "tokens", 90, 100, 86400)
    with pytest.raises(BudgetExceeded):
        charge("alice", "tokens", 11, 100, 86400)
    charge("alice", "tokens", 10, 100, 86400)
    monkeypatch.setattr("app.core.usage.time.time", lambda: 172801)
    charge("alice", "tokens", 100, 100, 86400)


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/agents/study/chat", {"message": "hello"}),
        ("/api/agents/study/chat/stream", {"message": "hello"}),
        ("/api/team/ask", {"question": "hello", "agent_ids": ["study"]}),
    ],
)
def test_authenticated_request_limit(client, make_user, monkeypatch, path, body):
    alice, bob = make_user("Alice"), make_user("Bob")
    enable(monkeypatch, [(alice, "a" * 40), (bob, "b" * 40)])
    monkeypatch.setattr(settings, "account_requests_per_minute", 1)
    headers = {"Origin": settings.frontend_url, "X-User-Id": bob.id}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=headers)
    assert client.post(path, json=body, headers=headers).status_code == 200
    denied = client.post(path, json=body, headers=headers)
    assert denied.status_code == 429
    assert int(denied.headers["Retry-After"]) > 0
    client.post("/api/auth/login", json={"access_key": "b" * 40}, headers=headers)
    assert client.post(path, json=body, headers=headers).status_code == 200


@pytest.mark.parametrize("stream", [False, True])
def test_daily_error_and_stream_scope(client, monkeypatch, stream):
    monkeypatch.setattr(settings, "account_daily_token_budget", 1)
    response = client.post(
        "/api/agents/study/chat" + ("/stream" if stream else ""), json={"message": "hello"}
    )
    assert "daily AI allowance" in response.text
    assert response.status_code == (200 if stream else 429)
    assert account_scope.get() is None


def test_team_charges_every_provider_call(client):
    response = client.post(
        "/api/team/ask", json={"question": "hello", "agent_ids": ["study", "career"]}
    )
    assert response.status_code == 200
    with SessionLocal() as db:
        bucket = db.scalar(select(UsageBucket).where(UsageBucket.kind == "tokens"))
        assert bucket.amount > 3 * 1024


def test_failed_provider_keeps_charge():
    from app.core.usage import BudgetedProvider

    class Broken:
        name = "broken"

        async def stream_chat(self, **kwargs):
            raise RuntimeError("disconnected")
            yield ""

    async def run():
        token = account_scope.set("alice")
        try:
            with pytest.raises(RuntimeError):
                async for _ in BudgetedProvider(Broken()).stream_chat(
                    system="hello", messages=[], model="test", temperature=0, max_tokens=100
                ):
                    pass
        finally:
            account_scope.reset(token)

    asyncio.run(run())
    with SessionLocal() as db:
        assert db.scalar(select(UsageBucket.amount).where(UsageBucket.account == "alice")) == 361


def _run_budgeted(inner, account="bob"):
    from app.core.usage import BudgetedProvider

    async def run():
        token = account_scope.set(account)
        got = []
        try:
            async for delta in BudgetedProvider(inner).stream_chat(
                system="hello", messages=[], model="test", temperature=0, max_tokens=100
            ):
                got.append(delta)
        except Exception as exc:  # noqa: BLE001 - the caller asserts on the type
            return got, exc
        finally:
            account_scope.reset(token)
        return got, None

    outcome = asyncio.run(run())
    with SessionLocal() as db:
        charged = db.scalar(select(UsageBucket.amount).where(UsageBucket.account == account))
    return outcome, charged


def test_a_provider_refusal_before_any_text_is_refunded():
    """Every failure offers "Try again"; charging each one would let a short
    outage use up a person's whole day for replies they never got."""
    from app.llm.openai_compat_provider import ProviderError

    class Refuses:
        name = "refuses"

        async def stream_chat(self, **kwargs):
            raise ProviderError("The AI provider could not respond (HTTP 503).")
            yield ""

    (_, error), charged = _run_budgeted(Refuses())
    assert isinstance(error, ProviderError)
    assert charged == 0


def test_a_reply_that_produced_text_stays_charged_even_if_cut_short():
    from app.llm.base import INTERRUPTED, StreamEnded

    class CutShort:
        name = "cut"

        async def stream_chat(self, **kwargs):
            yield "Half an answer"
            raise StreamEnded(INTERRUPTED, "dropped")

    (got, error), charged = _run_budgeted(CutShort(), account="carol")
    assert got == ["Half an answer"] and isinstance(error, StreamEnded)
    assert charged == 361, "tokens were spent on text the person received"


def test_the_account_allowance_is_still_enforced_after_refunds(monkeypatch):
    """A refund returns exactly what was taken, never more."""
    from app.llm.openai_compat_provider import ProviderError

    class Refuses:
        name = "refuses"

        async def stream_chat(self, **kwargs):
            raise ProviderError("refused")
            yield ""

    for _ in range(3):
        _run_budgeted(Refuses(), account="dave")
    (_, _), charged = _run_budgeted(Refuses(), account="dave")
    assert charged == 0


def test_memory_extraction_is_charged(client, monkeypatch):
    from app.llm.mock_provider import MockLLMProvider

    calls = []
    original = MockLLMProvider.stream_chat

    async def tracked(self, **kwargs):
        calls.append(kwargs)
        async for delta in original(self, **kwargs):
            yield delta

    monkeypatch.setattr(MockLLMProvider, "stream_chat", tracked)
    monkeypatch.setattr(settings, "memory_extraction", "llm")
    response = client.post("/api/agents/study/chat", json={"message": "I live in Cairo."})
    assert response.status_code == 200
    assert len(calls) == 2
    expected = sum(
        len(c["system"].encode())
        + sum(len(m.content.encode()) + 32 for m in c["messages"])
        + c["max_tokens"]
        + 256
        for c in calls
    )
    with SessionLocal() as db:
        assert db.scalar(select(UsageBucket.amount).where(UsageBucket.kind == "tokens")) == expected


def test_team_daily_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "account_daily_token_budget", 1)
    response = client.post("/api/team/ask", json={"question": "hello", "agent_ids": ["study"]})
    assert response.status_code == 429
    assert "daily AI allowance" in response.text
