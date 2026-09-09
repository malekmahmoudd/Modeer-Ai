"""The single shared agent runtime.

Every agent — Modeer and all nine specialists — runs through this. Agents are
configurations, never separate applications.

    persist user message
    -> load agent config
    -> load shared personal context + this agent's private memory + goals
    -> load conversation history
    -> build the context packet
    -> stream from the LLM
    -> persist assistant message (+ diagnostics)
    -> extract candidate memories from the user's message
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agents.context import build_context
from app.agents.schema import AgentConfig
from app.conversations import service as convo_service
from app.db.models import Conversation, User
from app.goals import service as goal_service
from app.llm.base import LLMProvider
from app.llm.provider import get_llm_provider, resolve_model
from app.memory import service as memory_service
from app.memory.extraction import extract_candidates


@dataclass(slots=True)
class RuntimeEvent:
    type: str  # "start" | "delta" | "end" | "error"
    data: dict

    def as_sse(self) -> str:
        import json

        return f"data: {json.dumps({'type': self.type, **self.data})}\n\n"


class AgentRuntime:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or get_llm_provider()

    async def run_stream(
        self,
        db: Session,
        user: User,
        agent: AgentConfig,
        conversation: Conversation,
        user_message: str,
    ) -> AsyncIterator[RuntimeEvent]:
        convo_service.add_message(db, conversation, "user", user_message)

        shared, agent_mem = memory_service.context_for_agent(db, user.id, agent)
        goals = goal_service.list_goals(db, user.id)
        history = convo_service.history(db, conversation.id)[:-1]  # exclude the one just added

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
        parts: list[str] = []
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
        except Exception as exc:  # noqa: BLE001 - surface provider failures to the client
            yield RuntimeEvent("error", {"error": f"{type(exc).__name__}: {exc}"})
            return

        answer = "".join(parts).strip() or "(no response)"
        meta = {
            "model": model,
            "provider": self._provider.name,
            "context": packet.diagnostics,
        }
        assistant_msg = convo_service.add_message(
            db, conversation, "assistant", answer, meta
        )

        candidates = extract_candidates(user_message, agent_id=agent.id)
        source = "modeer" if agent.is_assistant else agent.id
        memory_service.apply_candidates(db, user.id, candidates, source=source)
        db.commit()

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
            "end",
            {
                "conversation_id": conversation.id,
                "message_id": assistant_msg.id,
                "content": answer,
                "memory_candidates": stored,
                "context_used": packet.diagnostics["personal_context_count"] > 0
                or bool(packet.diagnostics["agent_memory_used"]),
            },
        )


runtime = AgentRuntime
