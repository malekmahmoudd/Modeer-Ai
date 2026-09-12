"""The single shared agent runtime.

Every agent — Modeer and all nine specialists — runs through this. Agents are
configurations, never separate applications.

    persist user message (or, on retry, reuse the unfinished turn's)
    -> load agent config
    -> load shared personal context + this agent's private memory + goals
    -> load conversation history
    -> build the context packet
    -> stream from the LLM
    -> persist assistant message (+ diagnostics and how it ended)
    -> extract candidate memories from the user's message

Every reply is saved with one of four completion states, so a reload shows
exactly what the live stream showed:

    completed    the provider finished the reply
    truncated    the reply hit its length limit; the text is kept
    interrupted  the stream stopped part-way; the text that arrived is kept
    failed       nothing usable arrived; an empty placeholder records it
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agents.context import build_context
from app.agents.schema import AgentConfig
from app.conversations import service as convo_service
from app.core.config import settings
from app.core.usage import BudgetExceeded
from app.db.models import Conversation, User
from app.goals import service as goal_service
from app.llm.base import COMPLETED, FAILED, INTERRUPTED, LLMProvider, StreamEnded
from app.llm.openai_compat_provider import ProviderError
from app.llm.provider import get_llm_provider, resolve_model
from app.memory import service as memory_service
from app.memory.extraction import extract_candidates
from app.memory.llm_extraction import llm_extract_candidates


@dataclass(slots=True)
class RuntimeEvent:
    type: str  # "start" | "delta" | "end" | "memory" | "error"
    data: dict

    def as_sse(self) -> str:
        import json

        return f"data: {json.dumps({'type': self.type, **self.data})}\n\n"


#: One turn at a time per conversation. A second "Try again" that arrives while
#: the first is still streaming waits here, and then finds the reply already
#: finished and is refused (409) — rather than answering the same message twice.
#: Process-local, which matches the single-process deployment; across several
#: processes this would have to be claimed in the database.
_turn_locks: dict[str, asyncio.Lock] = {}
_turn_waiting: Counter = Counter()


@asynccontextmanager
async def one_turn_at_a_time(conversation_id: str):
    lock = _turn_locks.setdefault(conversation_id, asyncio.Lock())
    _turn_waiting[conversation_id] += 1
    try:
        async with lock:
            yield
    finally:
        _turn_waiting[conversation_id] -= 1
        if _turn_waiting[conversation_id] <= 0:
            _turn_waiting.pop(conversation_id, None)
            _turn_locks.pop(conversation_id, None)


class AgentRuntime:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or get_llm_provider()

    async def run_stream(
        self,
        db: Session,
        user: User,
        agent: AgentConfig,
        conversation: Conversation,
        user_message: str | None,
        *,
        retry: bool = False,
    ) -> AsyncIterator[RuntimeEvent]:
        """Run one turn, or with ``retry`` regenerate the latest unfinished one.

        A retry reuses the turn's user message rather than writing it again, and
        only runs when the person asks: nothing here retries on its own. Turns in
        one conversation are serialised; see :func:`one_turn_at_a_time`.
        """
        async with one_turn_at_a_time(conversation.id):
            async for event in self._run_turn(
                db, user, agent, conversation, user_message, retry=retry
            ):
                yield event

    async def _run_turn(
        self,
        db: Session,
        user: User,
        agent: AgentConfig,
        conversation: Conversation,
        user_message: str | None,
        *,
        retry: bool = False,
    ) -> AsyncIterator[RuntimeEvent]:
        if retry:
            try:
                user_row = convo_service.prepare_retry(db, conversation)
            except convo_service.NothingToRetry as exc:
                yield RuntimeEvent(
                    "error", {"error": str(exc), "status": 409, "conversation_id": conversation.id}
                )
                return
            user_message = user_row.content
        else:
            user_row = convo_service.add_message(db, conversation, "user", user_message)

        shared, agent_mem = memory_service.context_for_agent(db, user.id, agent)
        goals = goal_service.list_goals(db, user.id)
        history = convo_service.history_for_model(
            [m for m in convo_service.history(db, conversation.id) if m.id != user_row.id]
        )

        packet = build_context(
            agent=agent,
            user=user,
            shared=shared,
            agent_memory=agent_mem,
            goals=goals,
            history=history,
            user_message=user_message,
        )
        db.commit()

        yield RuntimeEvent(
            "start",
            {
                "conversation_id": conversation.id,
                "agent_id": agent.id,
                "context": packet.diagnostics,
            },
        )

        model = resolve_model(agent.model.model)
        meta = {"model": model, "provider": self._provider.name, "context": packet.diagnostics}
        parts: list[str] = []
        completion, notice, status, retry_after = COMPLETED, "", 502, None
        try:
            async for delta in self._provider.stream_chat(
                system=packet.system,
                messages=packet.messages,
                model=model,
                temperature=agent.model.temperature,
                max_tokens=agent.model.max_tokens,
            ):
                if not delta:
                    continue
                parts.append(delta)
                yield RuntimeEvent("delta", {"text": delta})
        except StreamEnded as ended:
            # Text arrived, then the reply stopped short. Keep every word and
            # say plainly how it ended.
            completion, notice = ended.status, str(ended)
        except Exception as exc:  # noqa: BLE001 - surface provider failures to the client
            logging.getLogger(__name__).warning("Reply failed: %s", type(exc).__name__)
            completion = FAILED
            notice = (
                str(exc)
                if isinstance(exc, ProviderError)
                else "The reply was interrupted. Please try again."
            )
            status = 429 if isinstance(exc, BudgetExceeded) else 502
            retry_after = getattr(exc, "retry_after", None)
        except (asyncio.CancelledError, GeneratorExit):
            # The person's own connection closed mid-reply: a reload, a lost
            # network. Nobody is listening any more, but save what arrived so
            # the conversation shows it when they come back.
            _save_reply(db, conversation, "".join(parts).strip(), meta)
            raise

        answer = "".join(parts).strip()
        if not answer and completion != FAILED:
            completion, notice = FAILED, "The AI reply was empty. Please try again."
        meta["completion"] = completion
        if notice:
            meta["notice"] = notice
        assistant_msg = convo_service.add_message(db, conversation, "assistant", answer, meta)
        db.commit()

        if completion == FAILED:
            yield RuntimeEvent(
                "error",
                {
                    "error": notice,
                    "status": status,
                    "completion": FAILED,
                    "conversation_id": conversation.id,
                    "message_id": assistant_msg.id,
                    "retry_after": retry_after,
                },
            )
            return

        # The answer is done — release it now, then do memory work.
        yield RuntimeEvent(
            "end",
            {
                "conversation_id": conversation.id,
                "message_id": assistant_msg.id,
                "content": answer,
                "completion": completion,
                "notice": notice,
                "context_used": packet.diagnostics["personal_context_count"] > 0
                or bool(packet.diagnostics["agent_memory_used"]),
            },
        )

        # --- candidate memory extraction -------------------------------------
        # The reply is already saved and delivered. Nothing from here on may be
        # reported as a failed reply: if memory work breaks, say that memory
        # broke.
        try:
            # Once per user message. A retry of a turn that already got partway
            # has already learned from this message; asking again would spend
            # another provider call to learn nothing new.
            if (user_row.meta or {}).get("memory_extracted"):
                candidates = []
            elif settings.use_llm_extraction:
                try:
                    candidates = await asyncio.wait_for(
                        llm_extract_candidates(
                            user_message, agent_id=agent.id, provider=self._provider, model=model
                        ),
                        timeout=settings.memory_timeout_seconds,
                    )
                except TimeoutError:
                    candidates = extract_candidates(user_message, agent_id=agent.id)
            else:
                candidates = extract_candidates(user_message, agent_id=agent.id)
            # Reassign rather than mutate: the JSON column only notices a new object.
            user_row.meta = {**(user_row.meta or {}), "memory_extracted": True}

            source = "modeer" if agent.is_assistant else agent.id
            memory_service.apply_candidates(db, user.id, candidates, source=source)

            newly_onboarded = False
            if not user.onboarded:
                shared_count = len(memory_service.list_shared(db, user.id))
                assistant_turns = sum(
                    1
                    for m in convo_service.history_for_model(
                        convo_service.history(db, conversation.id)
                    )
                    if m.role == "assistant"
                )
                if shared_count >= 3 or (assistant_turns >= 4 and shared_count >= 1):
                    user.onboarded = True
                    newly_onboarded = True
            db.commit()
        except Exception as exc:  # noqa: BLE001 - the reply stands; memory does not
            logging.getLogger(__name__).warning("Memory update failed: %s", type(exc).__name__)
            db.rollback()
            yield RuntimeEvent(
                "memory",
                {
                    "conversation_id": conversation.id,
                    "memory_candidates": [],
                    "newly_onboarded": False,
                    "error": "Your reply was saved, but memory could not be updated.",
                },
            )
            return

        stored = [
            {
                "scope": c.scope,
                "agent_id": c.agent_id,
                "category": c.category,
                "key": c.key,
                "value": c.value,
                "confidence": c.confidence,
                "stored": c.stored,
                "reason": c.reason,
            }
            for c in candidates
        ]
        yield RuntimeEvent(
            "memory",
            {
                "conversation_id": conversation.id,
                "memory_candidates": stored,
                "newly_onboarded": newly_onboarded,
            },
        )


_CLOSED = "The connection closed before this reply finished."


def _save_reply(db: Session, conversation: Conversation, answer: str, meta: dict) -> None:
    """Record a reply whose listener went away, without letting a failure here
    mask the cancellation that is already under way."""
    completion = INTERRUPTED if answer else FAILED
    try:
        convo_service.add_message(
            db,
            conversation,
            "assistant",
            answer,
            {**meta, "completion": completion, "notice": _CLOSED},
        )
        db.commit()
    except Exception:  # noqa: BLE001 - best effort; the original exception wins
        db.rollback()
        logging.getLogger(__name__).warning("Could not save a reply cut off by the client")


runtime = AgentRuntime
