from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.briefings import service
from app.briefings.schemas import BriefingRead

router = APIRouter(prefix="/briefings", tags=["briefings"])


@router.get("/today", response_model=BriefingRead)
def today(user: CurrentUser, db: DbSession, refresh: bool = False):
    return service.get_or_generate_today(db, user, force=refresh)
