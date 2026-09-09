"""Provider-agnostic LLM interface.

Only streaming chat is required. Swap providers by implementing this one class
and wiring it in ``app/llm/provider.py``. No model routing, no multi-provider
fan-out for the MVP.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(slots=True)
class LLMMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    usage: dict[str, int]


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def stream_chat(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Yield text deltas as they arrive."""
        raise NotImplementedError

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResult:
        chunks: list[str] = []
        async for delta in self.stream_chat(
            system=system,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            chunks.append(delta)
        text = "".join(chunks)
        return LLMResult(
            text=text,
            model=model,
            usage={"approx_tokens": len(text.split())},
        )
