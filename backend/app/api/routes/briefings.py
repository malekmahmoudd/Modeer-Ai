from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, DbSession
from app.briefings import service
from app.briefings.schemas import BriefingRead
from app.core.lang import request_locale

router = APIRouter(prefix="/briefings", tags=["briefings"])


@router.get("/today", response_model=BriefingRead)
def today(user: CurrentUser, db: DbSession, request: Request, refresh: bool = False):
    return service.get_or_generate_today(
        db, user, force=refresh, locale=request_locale(request, user)
    )
