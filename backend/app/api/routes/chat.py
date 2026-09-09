from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.registry import get_agent
from app.agents.runtime import AgentRuntime
from app.conversations import service as convo_service
from app.conversations.schemas import ChatRequest
from app.db.session import SessionLocal
from app.users.service import get_by_id, get_or_create_demo_user

router = APIRouter(prefix="/agents", tags=["chat"])


def _resolve_user(db, x_user_id: str | None):
    if x_user_id:
        user = get_by_id(db, x_user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Unknown user")
        return user
    return get_or_create_demo_user(db)


@router.post("/{agent_id}/chat/stream")
async def chat_stream(
    agent_id: str,
    body: ChatRequest,
    x_user_id: Annotated[str | None, Header()] = None,
):
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Unknown agent")

    async def event_source():
        db = SessionLocal()
        try:
            user = _resolve_user(db, x_user_id)
            try:
                convo = convo_service.get_or_create(
                    db, user.id, agent_id, body.conversation_id
                )
            except (KeyError, ValueError) as exc:
                yield f'data: {{"type": "error", "error": "{exc}"}}\n\n'
                return
            db.commit()
            runtime = AgentRuntime()
            async for event in runtime.run_stream(
                db, user, agent, convo, body.message
            ):
                yield event.as_sse()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            yield f'data: {{"type": "error", "error": "{type(exc).__name__}: {exc}"}}\n\n'
        finally:
            db.close()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{agent_id}/chat")
async def chat_sync(
    agent_id: str,
    body: ChatRequest,
    x_user_id: Annotated[str | None, Header()] = None,
) -> dict:
    """Non-streaming convenience endpoint (used by tests and as a fallback)."""
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Unknown agent")

    db = SessionLocal()
    try:
        user = _resolve_user(db, x_user_id)
        try:
            convo = convo_service.get_or_create(
                db, user.id, agent_id, body.conversation_id
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.commit()

        runtime = AgentRuntime()
        collected = {"content": "", "context": {}, "memory_candidates": [],
                     "conversation_id": convo.id, "context_used": False}
        async for event in runtime.run_stream(db, user, agent, convo, body.message):
            if event.type == "start":
                collected["context"] = event.data.get("context", {})
            elif event.type == "end":
                collected.update(
                    content=event.data["content"],
                    memory_candidates=event.data["memory_candidates"],
                    context_used=event.data["context_used"],
                    message_id=event.data["message_id"],
                )
            elif event.type == "error":
                raise HTTPException(status_code=502, detail=event.data["error"])
        return collected
    finally:
        db.close()
