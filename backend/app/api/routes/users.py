from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import IntegrityError

from app.agents.registry import require_agent
from app.api.deps import CurrentUser, DbSession
from app.core.auth import COOKIE
from app.core.clock import today_for
from app.core.config import settings
from app.core.usage import limited_caller
from app.llm.provider import get_llm_provider, resolve_model
from app.memory import service as memory_service
from app.memory.extraction import extract_candidates
from app.memory.llm_extraction import analyze_turn
from app.users.schemas import ProfileUpdate, UserRead
from app.users.service import (
    EmailChangeRefused,
    delete_user,
    export_user_data,
    update_profile,
)

router = APIRouter(prefix="/users", tags=["users"])


class AboutMe(BaseModel):
    """A CV, a bio, or a few lines about yourself, to learn from in one go."""

    text: str = Field(min_length=10, max_length=20000)


class DeleteAccount(BaseModel):
    """Deleting an account is irreversible, so it takes a deliberate confirmation."""

    confirm: str = Field(description="Must be the exact word DELETE")


@router.get("/me", response_model=UserRead)
def get_me(user: CurrentUser) -> UserRead:
    return user


@router.patch("/me", response_model=UserRead)
def patch_me(data: ProfileUpdate, user: CurrentUser, db: DbSession) -> UserRead:
    try:
        return update_profile(db, user, data)
    except EmailChangeRefused as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail="; ".join(e["msg"] for e in exc.errors())
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="That email is already in use.") from exc


@router.get("/me/export")
def export_me(user: CurrentUser, db: DbSession) -> JSONResponse:
    """Download everything stored about this account as one JSON file.

    Sent as an attachment rather than a rendered body: this is the user's data
    to keep, and it contains the full text of every conversation.
    """
    payload = export_user_data(db, user)
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": 'attachment; filename="modeer-export.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/me/delete", status_code=204)
def delete_me(data: DeleteAccount, user: CurrentUser, db: DbSession, response: Response):
    """Erase this account and everything belonging to it. There is no undo.

    A POST rather than DELETE so the confirmation travels in a body that every
    client sends reliably, and so it cannot be triggered by a bare link.
    """
    if data.confirm != "DELETE":
        # 422 rather than 400: the body is the thing that is wrong.
        raise HTTPException(status_code=422, detail="Send confirm: DELETE to erase the account")
    delete_user(db, user)
    db.commit()
    response.delete_cookie(COOKIE, path="/api")


@router.post("/me/about")
async def about_me(
    # Charged first, before the account session opens a write of its own.
    _caller: Annotated[str | None, Depends(limited_caller)],
    data: AboutMe,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Learn from text the person says is about them — faster than onboarding by chat.

    Explicit, so it works with automatic memory off. Text sent here is not put
    through the paste guard: the person has said it is theirs. Facts they saved
    by hand are still never overwritten.
    """
    leo = require_agent("modeer")
    if settings.use_llm_extraction:
        # A refused or failed call (the daily allowance included) falls back to
        # the rule-based extractor inside analyze_turn.
        analysis = await analyze_turn(
            data.text,
            agent_id=leo.id,
            provider=get_llm_provider(),
            model=settings.memory_model or resolve_model(leo.model.model),
            today=today_for(user),
            known_keys=[r.key for r in memory_service.list_shared(db, user.id)],
            about_me=True,
        )
        candidates = analysis.facts
    else:
        candidates = extract_candidates(data.text, agent_id=leo.id)
    memory_service.apply_candidates(db, user.id, candidates, source=leo.id)
    return {
        "memory_candidates": [
            {
                "scope": c.scope,
                "agent_id": c.agent_id,
                "category": c.category,
                "key": c.key,
                "value": c.value,
                "stored": c.stored,
                "reason": c.reason,
                "previous_value": c.previous_value,
            }
            for c in candidates
        ]
    }
