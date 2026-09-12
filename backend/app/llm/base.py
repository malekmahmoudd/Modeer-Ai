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


#: How a reply ended. Carried from the provider to the user so that a partial
#: answer is never presented as a whole one, and a failure never as an answer.
COMPLETED = "completed"  # the provider finished normally
TRUNCATED = "truncated"  # useful text, then the token cap
INTERRUPTED = "interrupted"  # useful text, then the stream broke
FAILED = "failed"  # no usable text at all
COMPLETION_STATES = frozenset({COMPLETED, TRUNCATED, INTERRUPTED, FAILED})


class StreamEnded(Exception):  # noqa: N818 - an outcome, not an error
    """Raised by a provider AFTER it has yielded text that did not end normally.

    A generator cannot return a status alongside its values, so the status
    travels as this exception once the last chunk is out. Everything already
    yielded is real and should be kept; ``status`` says how far to trust it.
    Only :data:`TRUNCATED` and :data:`INTERRUPTED` are raised this way — a reply
    with no text is a plain provider error.
    """

    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    usage: dict[str, int]
    finish: str = COMPLETED


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
        """Collect a whole reply.

        A truncated reply is returned with ``finish=TRUNCATED``: the text is
        real, merely short. An interrupted one is re-raised — a caller that
        wanted the complete text (extraction, evaluation, synthesis) must not
        mistake half of it for the whole.
        """
        chunks: list[str] = []
        finish = COMPLETED
        try:
            async for delta in self.stream_chat(
                system=system,
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                chunks.append(delta)
        except StreamEnded as ended:
            if ended.status != TRUNCATED:
                raise
            finish = TRUNCATED
        text = "".join(chunks)
        return LLMResult(
            text=text,
            model=model,
            usage={"approx_tokens": len(text.split())},
            finish=finish,
        )
