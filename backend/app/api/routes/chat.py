from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agents.registry import get_agent
from app.agents.runtime import AgentRuntime
from app.conversations import service as convo_service
from app.conversations.schemas import ChatRequest
from app.core.auth import session_epoch_matches
from app.core.usage import account_scope, limited_caller
from app.db.session import SessionLocal
from app.users.service import get_by_id, get_or_create_demo_user

router = APIRouter(prefix="/agents", tags=["chat"])

CallerId = Annotated[str | None, Depends(limited_caller)]


def _resolve_user(db, x_user_id: str | None, request: Request | None = None):
    if x_user_id:
        user = get_by_id(db, x_user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Unknown user")
        if request is not None and not session_epoch_matches(request, user):
            raise HTTPException(status_code=401, detail="Please sign in")
        return user
    return get_or_create_demo_user(db)


@router.post("/{agent_id}/chat/stream")
async def chat_stream(
    agent_id: str,
    body: ChatRequest,
    x_user_id: CallerId,
    request: Request,
):
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Unknown agent")

    async def event_source():
        scope_token = account_scope.set(x_user_id or "local-demo")
        db = SessionLocal()
        try:
            user = _resolve_user(db, x_user_id, request)
            try:
                convo = convo_service.get_or_create(db, user.id, agent_id, body.conversation_id)
            except (KeyError, ValueError) as exc:
                yield f'data: {{"type": "error", "error": "{exc}"}}\n\n'
                return
            db.commit()
            runtime = AgentRuntime()
            async for event in runtime.run_stream(db, user, agent, convo, body.message):
                yield event.as_sse()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logging.getLogger(__name__).warning("Chat failure: %s", type(exc).__name__)
            yield (
                "data: "
                + json.dumps(
                    {"type": "error", "error": "The reply was interrupted. Please try again."}
                )
                + "\n\n"
            )
        finally:
            db.close()
            account_scope.reset(scope_token)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{agent_id}/chat")
async def chat_sync(
    agent_id: str,
    body: ChatRequest,
    x_user_id: CallerId,
    request: Request,
) -> dict:
    """Non-streaming convenience endpoint (used by tests and as a fallback)."""
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Unknown agent")

    db = SessionLocal()
    try:
        user = _resolve_user(db, x_user_id, request)
        try:
            convo = convo_service.get_or_create(db, user.id, agent_id, body.conversation_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.commit()

        runtime = AgentRuntime()
        collected = {
            "content": "",
            "context": {},
            "memory_candidates": [],
            "conversation_id": convo.id,
            "context_used": False,
            "newly_onboarded": False,
        }
        async for event in runtime.run_stream(db, user, agent, convo, body.message):
            if event.type == "start":
                collected["context"] = event.data.get("context", {})
            elif event.type == "end":
                collected.update(
                    content=event.data["content"],
                    context_used=event.data["context_used"],
                    message_id=event.data["message_id"],
                )
            elif event.type == "memory":
                collected.update(
                    memory_candidates=event.data["memory_candidates"],
                    newly_onboarded=event.data.get("newly_onboarded", False),
                )
            elif event.type == "error":
                raise HTTPException(
                    status_code=event.data.get("status", 502), detail=event.data["error"]
                )
        return collected
    finally:
        db.close()
