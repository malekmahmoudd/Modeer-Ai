from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.agents.registry import all_agents
from app.api.deps import DbSession
from app.core.config import settings
from app.core.observability import health as health_counters

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


@router.get("/health/detail")
def health_detail(db: DbSession, response: Response) -> dict:
    """Readiness plus what this process has seen since it started.

    Public on purpose: it exposes counts and timings, never content, and an
    uptime check that needs a credential is one more thing to break at 3am.
    """
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False

    try:
        applied = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001 - SQLite dev databases never ran alembic
        applied = None

    counters = health_counters.snapshot()
    ready = db_ok and not _erroring(counters)
    if settings.environment == "production" and applied != "0003":
        ready = False
    response.status_code = 200 if ready else 503
    return {
        "status": "ok" if ready else "degraded",
        "database": "ok" if db_ok else "error",
        "schema_revision": applied,
        "environment": settings.environment,
        "auth_required": settings.auth_required,
        **counters,
    }


def _erroring(counters: dict) -> bool:
    """More than a handful of unhandled errors is degraded, not ok."""
    last = counters.get("last_error")
    recent = bool(
        last
        and last.get("at")
        and (datetime.now(UTC) - datetime.fromisoformat(last["at"])).total_seconds() < 900
    )
    return bool(
        counters["provider"].get("blocked_models") or counters["provider"].get("failed_models")
    ) or (counters["unhandled_errors"] >= settings.alert_error_threshold and recent)
