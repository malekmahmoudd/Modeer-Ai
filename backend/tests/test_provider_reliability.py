import asyncio
import json

import httpx
import pytest

from app.core.config import settings
from app.llm.base import COMPLETED, INTERRUPTED, TRUNCATED, StreamEnded
from app.llm.openai_compat_provider import OpenAICompatProvider, ProviderError


def run(monkeypatch, response):
    original = httpx.AsyncClient
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return response

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )

    async def collect():
        p = OpenAICompatProvider(name="groq", api_key="secret")
        return "".join(
            [
                x
                async for x in p.stream_chat(
                    system="test",
                    messages=[],
                    model="openai/gpt-oss-120b",
                    temperature=0,
                    max_tokens=100,
                )
            ]
        )

    return collect, captured


def test_rate_limit_fast_safe_error(monkeypatch):
    call, _ = run(
        monkeypatch,
        httpx.Response(
            429, headers={"retry-after": "120"}, json={"error": "private upstream details"}
        ),
    )
    with pytest.raises(ProviderError, match="usage limit") as e:
        asyncio.run(call())
    assert "private" not in str(e.value)


@pytest.fixture
def counters(monkeypatch):
    from app.core import observability as obs

    fresh = obs.Health()
    monkeypatch.setattr(obs, "health", fresh)
    monkeypatch.setattr(obs, "notify", lambda *a, **k: None)
    return fresh


def test_throttling_is_not_counted_as_a_provider_failure(monkeypatch, counters):
    """A per-minute 429 is the provider pacing us, not the provider failing."""
    call, _ = run(monkeypatch, httpx.Response(429, headers={"retry-after": "20"}))
    with pytest.raises(ProviderError):
        asyncio.run(call())
    assert counters.provider_rate_limits == 1
    assert counters.provider_failures == 0
    assert not counters.provider_failure_streak


def test_a_provider_failure_is_counted_but_only_a_run_of_them_is_sustained(monkeypatch, counters):
    from app.core.observability import PROVIDER_FAILURE_STREAK

    call, _ = run(monkeypatch, httpx.Response(503))
    with pytest.raises(ProviderError):
        asyncio.run(call())
    assert counters.provider_failures == 1
    assert counters.snapshot()["provider"]["failed_models"] == {}, "one 503 paged someone"

    for _ in range(PROVIDER_FAILURE_STREAK - 1):
        with pytest.raises(ProviderError):
            asyncio.run(call())
    assert list(counters.snapshot()["provider"]["failed_models"]) == ["openai/gpt-oss-120b"]


def test_reasoning_and_complete_stream(monkeypatch):
    call, payload = run(
        monkeypatch,
        httpx.Response(
            200,
            text=(
                "data: "
                '{"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}'
                "\n\ndata: [DONE]\n\n"
            ),
        ),
    )
    assert asyncio.run(call()) == "Hello"
    assert payload["reasoning_effort"] == "low"
    assert payload["max_completion_tokens"] == 612


def outcome(monkeypatch, body: str):
    """Stream a canned response; return (text kept, completion status).

    Unlike ``run``, this keeps the chunks that arrived before a StreamEnded, which
    is the whole point: a truncated or interrupted reply is real text.
    """
    run(monkeypatch, httpx.Response(200, text=body))  # installs the mock transport

    async def go():
        provider = OpenAICompatProvider(name="groq", api_key="secret")
        chunks: list[str] = []
        try:
            async for chunk in provider.stream_chat(
                system="test",
                messages=[],
                model="openai/gpt-oss-120b",
                temperature=0,
                max_tokens=100,
            ):
                chunks.append(chunk)
        except StreamEnded as ended:
            return "".join(chunks), ended.status
        return "".join(chunks), COMPLETED

    return asyncio.run(go())


def _event(content: str | None, finish: str | None = None) -> str:
    delta = {"content": content} if content is not None else {}
    return "data: " + json.dumps({"choices": [{"delta": delta, "finish_reason": finish}]}) + "\n\n"


def test_final_event_content_is_kept_before_its_finish_reason(monkeypatch):
    """The last words and the stop signal can arrive together; both must count."""
    text, status = outcome(monkeypatch, _event("Hello") + _event(" world.", "stop"))
    assert (text, status) == ("Hello world.", COMPLETED)


def test_hitting_the_token_cap_keeps_every_word_including_the_last_event(monkeypatch):
    """This test used to assert the reply ended at "ran" — pinning the bug that
    dropped the final event's words. The whole reply is kept and labelled."""
    text, status = outcome(
        monkeypatch, _event("A long answer that ran") + _event(" out of room", "length")
    )
    assert text == "A long answer that ran out of room"
    assert status == TRUNCATED


def test_a_stream_that_stops_without_finishing_is_interrupted_not_complete(monkeypatch):
    text, status = outcome(monkeypatch, _event("Half a reply"))
    assert (text, status) == ("Half a reply", INTERRUPTED)


def test_an_upstream_error_after_text_is_interrupted_and_keeps_the_text(monkeypatch):
    text, status = outcome(
        monkeypatch, _event("Partial") + 'data: {"error": {"message": "upstream"}}\n\n'
    )
    assert (text, status) == ("Partial", INTERRUPTED)


def test_an_upstream_error_before_any_text_is_a_failure(monkeypatch):
    with pytest.raises(ProviderError, match="interrupted"):
        outcome(monkeypatch, 'data: {"error": {"message": "upstream"}}\n\n')


def test_the_cap_consumed_with_nothing_emitted_is_a_failure(monkeypatch):
    """Reasoning tokens eating the whole budget leaves the user with nothing."""
    with pytest.raises(ProviderError, match="empty"):
        outcome(monkeypatch, _event(None, "length"))


def test_an_empty_completed_stream_is_a_failure_not_a_reply(monkeypatch):
    with pytest.raises(ProviderError, match="empty"):
        outcome(monkeypatch, _event("", "stop") + "data: [DONE]\n\n")


def _paced_stream(gap: float, chunks: int = 6):
    """A stream that keeps arriving, one event every `gap` seconds."""

    async def body():
        for i in range(chunks):
            yield _event(f"word{i} ").encode()
            await asyncio.sleep(gap)
        yield _event(None, "stop").encode() + b"data: [DONE]\n\n"

    return body


def _stream_with(monkeypatch, body, total: float, idle: float):
    import app.llm.openai_compat_provider as provider_module

    monkeypatch.setattr(settings, "llm_timeout_seconds", total)
    monkeypatch.setattr(provider_module, "_IDLE_SECONDS", idle)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body())), **kw
        ),
    )

    async def go():
        got = []
        try:
            async for chunk in OpenAICompatProvider(name="groq", api_key="x").stream_chat(
                system="s", messages=[], model="m", temperature=0, max_tokens=50
            ):
                got.append(chunk)
        except StreamEnded as ended:
            return "".join(got), ended.status, str(ended)
        return "".join(got), COMPLETED, ""

    return asyncio.run(go())


def test_a_slow_first_token_gets_the_whole_budget_not_the_idle_window(monkeypatch):
    """Waiting for the first token is queueing, not silence. The idle window
    briefly applied to it too, which would have failed replies that a busy free
    tier simply had not started yet."""

    async def late_start():
        await asyncio.sleep(1.0)
        yield _event("here ").encode()
        yield _event(None, "stop").encode() + b"data: [DONE]\n\n"

    text, status, notice = _stream_with(monkeypatch, lambda: late_start(), total=5.0, idle=0.3)
    assert (text, status, notice) == ("here ", COMPLETED, "")


def test_a_stream_that_goes_quiet_says_the_provider_stopped_responding(monkeypatch):
    text, status, notice = _stream_with(
        monkeypatch, _paced_stream(gap=5.0, chunks=3), total=30.0, idle=0.3
    )
    assert (status, text) == (INTERRUPTED, "word0 ")
    assert "stopped responding" in notice


def test_a_stream_still_arriving_at_the_time_limit_says_so_instead(monkeypatch):
    """It was blaming the provider for going quiet while it was still sending."""
    text, status, notice = _stream_with(
        monkeypatch, _paced_stream(gap=0.05, chunks=40), total=0.4, idle=0.3
    )
    assert status == INTERRUPTED
    assert "ran past the time limit" in notice
    assert text.startswith("word0 word1"), "the words that did arrive are kept"


def test_complete_returns_a_truncated_reply_with_its_status(monkeypatch):
    run(monkeypatch, httpx.Response(200, text=_event("Long") + _event(" reply", "length")))

    async def go():
        provider = OpenAICompatProvider(name="groq", api_key="secret")
        return await provider.complete(
            system="t", messages=[], model="openai/gpt-oss-120b", temperature=0, max_tokens=10
        )

    result = asyncio.run(go())
    assert (result.text, result.finish) == ("Long reply", TRUNCATED)


def test_complete_does_not_pass_off_an_interrupted_reply_as_whole(monkeypatch):
    run(monkeypatch, httpx.Response(200, text=_event("Half")))

    async def go():
        provider = OpenAICompatProvider(name="groq", api_key="secret")
        return await provider.complete(
            system="t", messages=[], model="openai/gpt-oss-120b", temperature=0, max_tokens=10
        )

    with pytest.raises(StreamEnded):
        asyncio.run(go())


def test_reported_usage_reaches_the_budget_and_is_requested(monkeypatch):
    from app.llm.openai_compat_provider import usage_sink

    body = (
        'data: {"choices":[{"delta":{"content":"Hi"},"finish_reason":"stop"}]}\n\n'
        'data: {"choices":[],"usage":{"total_tokens":321}}\n\n'
        "data: [DONE]\n\n"
    )
    call, captured = run(monkeypatch, httpx.Response(200, text=body))
    sink: dict = {}

    async def collect():
        usage_sink.set(sink)
        return await call()

    assert asyncio.run(collect()) == "Hi"
    assert captured["stream_options"] == {"include_usage": True}
    assert sink == {"total_tokens": 321}
