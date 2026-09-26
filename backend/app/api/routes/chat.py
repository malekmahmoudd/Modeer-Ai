from __future__ import annotations

import json
import logging
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agents.registry import get_agent
from app.agents.runtime import AgentRuntime
from app.api.deps import refuse_if_suspended
from app.conversations import service as convo_service
from app.conversations.schemas import ChatRequest
from app.core.clock import valid_zone
from app.core.config import settings
from app.core.sessions import session_ok
from app.core.usage import account_scope, limited_caller
from app.db.session import SessionLocal
from app.users.service import get_by_id, get_or_create_demo_user

router = APIRouter(prefix="/agents", tags=["chat"])

CallerId = Annotated[str | None, Depends(limited_caller)]


def _resolve_user(db, x_user_id: str | None, request: Request | None = None):
    user = _find_user(db, x_user_id, request)
    if request is not None:
        # The browser reports its IANA zone with each message, so the agents
        # know what day it is for this person. Saved only when it changes.
        reported = valid_zone(request.headers.get("x-timezone"))
        if reported and reported != user.timezone:
            user.timezone = reported
    return user


def _find_user(db, x_user_id: str | None, request: Request | None):
    if x_user_id:
        user = get_by_id(db, x_user_id)
        if user is None:
            if settings.auth_required:  # see app.api.deps.get_current_user
                raise HTTPException(status_code=401, detail="Please sign in")
            raise HTTPException(status_code=404, detail="Unknown user")
        if request is not None and not session_ok(db, request, user):
            raise HTTPException(status_code=401, detail="Please sign in")
        refuse_if_suspended(user)
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

    # Resolve the account and the conversation BEFORE the stream starts. Inside
    # the generator the response is already a 200, so a 401 could only be sent
    # as an error event in the body — which a client reads as "the reply broke",
    # not "sign in again", and a revoked session then retries forever.
    db = SessionLocal()
    try:
        user = _resolve_user(db, x_user_id, request)
        try:
            convo = convo_service.get_or_create(
                db,
                user.id,
                agent_id,
                body.conversation_id,
                incognito=body.incognito,
                incognito_context=body.incognito_context,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Conversation not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.commit()
    except BaseException:
        db.close()
        raise

    async def event_source():
        scope_token = account_scope.set(x_user_id or "local-demo")
        try:
            runtime = AgentRuntime()
            # aclosing: when the client goes away, the runtime is closed here and
            # saves what arrived before this session closes — not whenever the
            # garbage collector gets round to it.
            turn = runtime.run_stream(
                db, user, agent, convo, body.message, retry=body.retry, attachments=body.attachments
            )
            async with aclosing(turn):
                async for event in turn:
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
    """Non-streaming convenience endpoint for tests and local tools.

    No screen uses it, so production does not serve it: an unused route is
    still something to keep correct and defend. Checked after authentication,
    like Ask My Team, so an anonymous caller still gets 401.
    """
    if settings.environment == "production":
        raise HTTPException(status_code=404, detail="Not Found")
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Unknown agent")

    db = SessionLocal()
    try:
        user = _resolve_user(db, x_user_id, request)
        try:
            convo = convo_service.get_or_create(
                db,
                user.id,
                agent_id,
                body.conversation_id,
                incognito=body.incognito,
                incognito_context=body.incognito_context,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        db.commit()

        runtime = AgentRuntime()
        collected = {
            "content": "",
            "completion": "completed",
            "notice": "",
            "context": {},
            "memory_candidates": [],
            "goal_changes": [],
            "handoffs": [],
            "conversation_id": convo.id,
            "context_used": False,
            "newly_onboarded": False,
        }
        turn = runtime.run_stream(
            db, user, agent, convo, body.message, retry=body.retry, attachments=body.attachments
        )
        async for event in turn:
            if event.type == "start":
                collected["context"] = event.data.get("context", {})
            elif event.type == "end":
                collected.update(
                    content=event.data["content"],
                    completion=event.data["completion"],
                    notice=event.data["notice"],
                    context_used=event.data["context_used"],
                    message_id=event.data["message_id"],
                )
            elif event.type == "memory":
                # Everything the memory event reports: facts, goal changes,
                # handoffs, follow-ups, check-ins, plans, the allowance.
                collected.update(
                    {k: v for k, v in event.data.items() if k not in ("conversation_id", "error")}
                )
            elif event.type == "error":
                raise HTTPException(
                    status_code=event.data.get("status", 502), detail=event.data["error"]
                )
        return collected
    finally:
        db.close()
