from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.agents.registry import all_agents
from app.api.deps import DbSession
from app.core.config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: DbSession) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "agents": len(all_agents()),
        "environment": settings.environment,
    }
