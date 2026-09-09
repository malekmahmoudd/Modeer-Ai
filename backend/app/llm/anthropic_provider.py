"""Anthropic Messages API provider (streaming).

The one real provider wired for the MVP. Kept deliberately small; the abstraction
in ``base.py`` is where a different vendor would plug in later.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.llm.base import LLMMessage, LLMProvider

_DEFAULT_BASE = "https://api.anthropic.com"
_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, base_url: str = "") -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY is required for the anthropic provider")
        self._api_key = api_key
        self._base_url = (base_url or _DEFAULT_BASE).rstrip("/")

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
            "system": system,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _VERSION,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=120.0)) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/messages",
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    detail = (await resp.aread()).decode("utf-8", "replace")
                    raise RuntimeError(f"Anthropic API {resp.status_code}: {detail}")
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
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")
