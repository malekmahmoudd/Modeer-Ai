"""OpenAI-compatible chat-completions provider (streaming).

Works with any endpoint that speaks the OpenAI `/chat/completions` protocol —
Groq, OpenAI, Together, Fireworks, local servers, etc. Selected by
`LLM_PROVIDER=groq` or `LLM_PROVIDER=openai`; the base URL can be overridden with
`LLM_BASE_URL`.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator

import httpx

from app.llm.base import LLMMessage, LLMProvider

_RETRY_HINT = re.compile(r"try again in ([0-9.]+)s")
_MAX_RETRIES = 4
_MAX_BACKOFF = 30.0

_DEFAULT_BASE = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
}


class OpenAICompatProvider(LLMProvider):
    def __init__(self, *, name: str, api_key: str, base_url: str = "") -> None:
        if not api_key:
            raise ValueError(f"LLM_API_KEY is required for the {name} provider")
        self.name = name
        self._api_key = api_key
        self._base_url = (base_url or _DEFAULT_BASE.get(name, "")).rstrip("/")
        if not self._base_url:
            raise ValueError(f"LLM_BASE_URL is required for the {name} provider")

    async def stream_chat(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                *({"role": m.role, "content": m.content} for m in messages),
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=180.0)) as client:
            for attempt in range(_MAX_RETRIES + 1):
                emitted = False
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as resp:
                    if resp.status_code == 429 and attempt < _MAX_RETRIES:
                        body = (await resp.aread()).decode("utf-8", "replace")
                        await asyncio.sleep(_retry_after(resp, body))
                        continue
                    if resp.status_code >= 400:
                        detail = (await resp.aread()).decode("utf-8", "replace")
                        raise RuntimeError(
                            f"{self.name} API {resp.status_code}: {detail[:500]}"
                        )
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = event.get("choices") or []
                        if not choices:
                            continue
                        text = (choices[0].get("delta") or {}).get("content")
                        if text:
                            emitted = True
                            yield text
                if emitted or resp.status_code != 429:
                    return


def _retry_after(resp: httpx.Response, body: str) -> float:
    header = resp.headers.get("retry-after")
    if header:
        try:
            return min(float(header), _MAX_BACKOFF)
        except ValueError:
            pass
    hint = _RETRY_HINT.search(body)
    if hint:
        return min(float(hint.group(1)) + 0.5, _MAX_BACKOFF)
    return 5.0
