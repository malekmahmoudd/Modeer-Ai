"""Bounded OpenAI-compatible streaming with safe, actionable errors."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.core.observability import (
    record_length_stop,
    record_provider_failure,
    record_provider_success,
    record_rate_limit,
)
from app.llm.base import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)
_DEFAULT_BASE = {"groq": "https://api.groq.com/openai/v1", "openai": "https://api.openai.com/v1"}


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
            payload["max_completion_tokens"] = max_tokens + 512
            payload["reasoning_effort"] = settings.llm_reasoning_effort
        else:
            payload["max_tokens"] = max_tokens
        started = time.monotonic()
        emitted = False
        finished = False
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
                        async for line in response.aiter_lines():
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
                                raise ProviderError(
                                    "The AI provider interrupted the reply. Please try again."
                                )
                            choices = event.get("choices") or []
                            if not choices:
                                continue
                            choice = choices[0]
                            reason = choice.get("finish_reason")
                            if reason == "length":
                                # Keep what has already streamed. Discarding a
                                # long, useful reply because the model ran to
                                # its cap is worse for the reader than ending a
                                # sentence early, and it is what made max_tokens
                                # unusable as a length control. Only a cap hit
                                # with nothing emitted is a real failure, and
                                # that falls through to the check below.
                                logger.info("provider=%s stopped at token cap", self.name)
                                record_length_stop(model)
                                finished = True
                                break
                            if reason:
                                finished = True
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
            if not emitted or not finished:
                raise ProviderError("The AI reply was incomplete. Please try again.")
            record_provider_success(model)
        except ProviderError:
            record_provider_failure(model)
            raise
        except (TimeoutError, httpx.TimeoutException) as exc:
            record_provider_failure(model)
            raise ProviderError(
                "The AI provider took too long to reply. Please try again."
            ) from exc
        except httpx.RequestError as exc:
            record_provider_failure(model)
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
