import asyncio
import json

import httpx
import pytest

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


def test_truncated_connection_is_not_success(monkeypatch):
    call, _ = run(
        monkeypatch,
        httpx.Response(200, text='data: {"choices":[{"delta":{"content":"Half a reply"}}]}\n\n'),
    )
    with pytest.raises(ProviderError, match="incomplete"):
        asyncio.run(call())
