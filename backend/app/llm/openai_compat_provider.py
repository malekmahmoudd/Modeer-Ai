"""Bounded OpenAI-compatible streaming with safe, actionable errors."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections.abc import AsyncIterator
from contextvars import ContextVar

import httpx

from app.core.config import settings
from app.core.observability import (
    record_length_stop,
    record_provider_failure,
    record_provider_success,
    record_rate_limit,
)
from app.llm.base import INTERRUPTED, TRUNCATED, LLMMessage, LLMProvider, StreamEnded

logger = logging.getLogger(__name__)
_DEFAULT_BASE = {"groq": "https://api.groq.com/openai/v1", "openai": "https://api.openai.com/v1"}
_DROPPED = "The connection to the AI provider dropped before this reply finished."
_STALLED = "The AI provider stopped responding before this reply finished."
_TOO_LONG = "This reply ran past the time limit and was cut short."
#: Silence between stream events that means the provider has stopped sending,
#: as opposed to a long reply still arriving. Capped by LLM_TIMEOUT_SECONDS.
_IDLE_SECONDS = 15.0


#: Where a call reports the token usage the provider returned. The budget
#: wrapper sets a fresh dict before each call and trues its charge up from it.
usage_sink: ContextVar[dict | None] = ContextVar("usage_sink", default=None)

#: Extra completion room Groq's gpt-oss models get for hidden reasoning.
_REASONING_ALLOWANCE = 512


def reasoning_allowance(model: str) -> int:
    """Tokens a model may spend reasoning on top of the visible reply cap."""
    return _REASONING_ALLOWANCE if model.startswith("openai/gpt-oss") else 0


class ProviderError(RuntimeError):
    """Safe to display; never includes upstream bodies, credentials or prompts.

    ``retry_after`` carries the upstream header's value in seconds when there was
    one. It is a number, not upstream text, so it leaks nothing — and it lets an
    unattended caller tell a minute-long throttle apart from a daily quota that
    no amount of waiting will clear.
    """

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class OpenAICompatProvider(LLMProvider):
    def __init__(self, *, name: str, api_key: str, base_url: str = "") -> None:
        if not api_key:
            raise ValueError(f"LLM_API_KEY is required for the {name} provider")
        self.name = name
        self._api_key = api_key
        self._base_url = (base_url or _DEFAULT_BASE.get(name, "")).rstrip("/")
        if not self._base_url:
            raise ValueError("LLM_BASE_URL is required")

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
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                *({"role": m.role, "content": m.content} for m in messages),
            ],
        }
        if model.startswith("openai/gpt-oss") and self.name == "groq":
            payload["max_completion_tokens"] = max_tokens + reasoning_allowance(model)
            payload["reasoning_effort"] = settings.llm_reasoning_effort
        else:
            payload["max_tokens"] = max_tokens
        if self.name in ("groq", "openai"):
            # Ask for the real token count in the final event, so the account
            # is charged for what was used rather than the up-front estimate.
            payload["stream_options"] = {"include_usage": True}
        sink = usage_sink.get()
        started = time.monotonic()
        emitted = False
        finished = False
        truncated = False
        interrupted = False
        throttled = False
        idle_guard: asyncio.Timeout | None = None
        idle_seconds = min(_IDLE_SECONDS, settings.llm_timeout_seconds)
        try:
            async with asyncio.timeout(settings.llm_timeout_seconds):
                async with httpx.AsyncClient(timeout=httpx.Timeout(15, read=20)) as client:
                    async with client.stream(
                        "POST",
                        f"{self._base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=payload,
                    ) as response:
                        logger.info(
                            "provider=%s status=%s remaining_tokens=%s retry_after=%s",
                            self.name,
                            response.status_code,
                            response.headers.get("x-ratelimit-remaining-tokens", "unknown"),
                            response.headers.get("retry-after", "none"),
                        )
                        if response.status_code == 429:
                            # Records the throttle and alerts the operator when
                            # the retry-after says the daily budget is spent.
                            record_rate_limit(_retry_after(response), model)
                            throttled = True
                            wait = _retry_after(response)
                            advice = (
                                f"Please try again in about {math.ceil(wait / 60)} "
                                f"{'minute' if math.ceil(wait / 60) == 1 else 'minutes'}."
                                if wait
                                else "Please try again later."
                            )
                            raise ProviderError(
                                "The AI provider is at its usage limit. " + advice, retry_after=wait
                            )
                        if response.status_code >= 400:
                            raise ProviderError(
                                f"The AI provider could not respond (HTTP {response.status_code}). "
                                "Please try again later."
                            )
                        # Two clocks, because they mean different things: the
                        # outer one caps the whole reply, this one fires when the
                        # provider goes quiet mid-stream. The notice below says
                        # which happened instead of blaming the provider for both.
                        #
                        # It starts at the full budget on purpose: the wait for
                        # the FIRST token is queueing, not silence, and a busy
                        # free tier can sit there for a while. Only once words
                        # are flowing does a gap mean the provider stopped.
                        async with asyncio.timeout(settings.llm_timeout_seconds) as idle_guard:
                            async for line in response.aiter_lines():
                                idle_guard.reschedule(
                                    asyncio.get_running_loop().time() + idle_seconds
                                )
                                if not line.startswith("data:"):
                                    continue
                                data = line[5:].strip()
                                if data == "[DONE]":
                                    finished = True
                                    break
                                if not data:
                                    continue
                                try:
                                    event = json.loads(data)
                                except ValueError:
                                    continue
                                if event.get("error"):
                                    interrupted = True
                                    break
                                usage = event.get("usage") or (event.get("x_groq") or {}).get(
                                    "usage"
                                )
                                if sink is not None and isinstance(usage, dict):
                                    total = usage.get("total_tokens")
                                    if isinstance(total, int):
                                        sink["total_tokens"] = total
                                choices = event.get("choices") or []
                                if not choices:
                                    continue
                                choice = choices[0]
                                # Content first, finish reason second: the provider
                                # may put the last words and the stop signal in the
                                # same event, and handling the reason first dropped
                                # those words — exactly at the end of a reply.
                                text = (choice.get("delta") or {}).get("content")
                                if text:
                                    if not emitted:
                                        logger.info(
                                            "provider=%s first_text_seconds=%.2f",
                                            self.name,
                                            time.monotonic() - started,
                                        )
                                    emitted = True
                                    yield text
                                reason = choice.get("finish_reason")
                                if reason == "length":
                                    logger.info("provider=%s stopped at token cap", self.name)
                                    record_length_stop(model)
                                    truncated = True
                                    break
                                if reason:
                                    finished = True
            if not emitted:
                # Nothing usable arrived, however it ended: a failure, not a reply.
                raise ProviderError(
                    "The AI provider interrupted the reply. Please try again."
                    if interrupted
                    else "The AI reply was empty. Please try again."
                )
            if truncated:
                # The provider answered fine; the reply was just long. Keep it.
                record_provider_success(model)
                raise StreamEnded(
                    TRUNCATED, "This reply reached its length limit and may be incomplete."
                )
            if interrupted or not finished:
                record_provider_failure(model)
                raise StreamEnded(INTERRUPTED, _DROPPED)
            record_provider_success(model)
        except StreamEnded:
            raise
        except ProviderError:
            if not throttled:  # throttling has its own record, above
                record_provider_failure(model)
            raise
        except (TimeoutError, httpx.TimeoutException) as exc:
            record_provider_failure(model)
            if emitted:
                went_quiet = idle_guard is not None and idle_guard.expired()
                raise StreamEnded(INTERRUPTED, _STALLED if went_quiet else _TOO_LONG) from exc
            raise ProviderError(
                "The AI provider took too long to reply. Please try again."
            ) from exc
        except httpx.RequestError as exc:
            record_provider_failure(model)
            if emitted:
                raise StreamEnded(INTERRUPTED, _DROPPED) from exc
            raise ProviderError("Could not reach the AI provider. Please try again.") from exc
        finally:
            logger.info(
                "provider=%s elapsed_seconds=%.2f completed=%s",
                self.name,
                time.monotonic() - started,
                finished,
            )


def _retry_after(response: httpx.Response) -> float | None:
    """The upstream retry-after header in seconds, when it sent a usable one."""
    try:
        value = float(response.headers.get("retry-after", ""))
        return value if math.isfinite(value) and value > 0 else None
    except ValueError:
        return None
