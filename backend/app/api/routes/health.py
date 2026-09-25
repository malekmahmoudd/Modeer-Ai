from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request, Response
from sqlalchemy import text

from app.agents.registry import all_agents
from app.api.deps import DbSession
from app.core.auth import COOKIE, session_claims
from app.core.clock import zone
from app.core.config import settings
from app.core.observability import health as health_counters
from app.documents.embedding import get_embedder
from app.users.service import get_by_id

router = APIRouter(tags=["system"])

#: backend/app/api/routes/health.py -> backend/ -> migrations/. The scripts ship
#: inside the image (the Docker build context is backend/), so this is always
#: the set of migrations the running code was built against.
_MIGRATIONS = Path(__file__).resolve().parents[3] / "migrations"


@lru_cache(maxsize=1)
def expected_schema_revisions() -> frozenset[str]:
    """The migration head(s) this build expects the database to be at.

    Read from the migration scripts rather than written down. It used to be a
    literal ``"0003"``, which meant the next migration would have left
    production reporting degraded forever on a healthy app — and a watchdog
    that alerts on nothing trains you to ignore it.

    Empty if the scripts cannot be read. Production treats that as not ready:
    a process that cannot tell which schema it expects cannot claim to be on it.
    """
    try:
        return frozenset(ScriptDirectory(str(_MIGRATIONS)).get_heads())
    except Exception:  # noqa: BLE001 - reported as not-ready, never raised
        return frozenset()


@router.get("/health")
def health(db: DbSession) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    body = {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
    }
    if settings.environment != "production":
        # Handy on a development machine; in production the provider, model and
        # environment are nobody's business but the operator's.
        body |= {
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "agents": len(all_agents()),
            "environment": settings.environment,
        }
    return body


@router.get("/health/detail")
def health_detail(db: DbSession, response: Response, request: Request) -> dict:
    """Readiness, and — for an operator — what this process has seen since start.

    The status code and ``status`` stay public: an uptime check that needs a
    credential is one more thing to break at 3am, and the watchdog reads only
    those. The counters, model names, incident ids and error types are for an
    admin: they describe the deployment's weak moments to anyone who asks.
    """
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False

    try:
        # All rows, not the first: a branched history has one row per head.
        applied = frozenset(
            db.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        )
    except Exception:  # noqa: BLE001 - SQLite dev databases never ran alembic
        applied = frozenset()
    expected = expected_schema_revisions()
    schema_current = bool(expected) and applied == expected

    counters = health_counters.snapshot()
    ready = db_ok and not _erroring(counters)
    if settings.environment == "production" and not schema_current:
        ready = False
    # Without a timezone database every user silently gets UTC: agents then
    # count days wrong for anyone far from Greenwich. Visible here, not silent.
    timezones_ok = zone("Asia/Riyadh") is not None
    if settings.environment == "production" and not timezones_ok:
        ready = False
    response.status_code = 200 if ready else 503
    public = {
        "status": "ok" if ready else "degraded",
        "database": "ok" if db_ok else "error",
        "schema_current": schema_current,
    }
    if not _operator(request, db):
        return public
    return {
        **public,
        "schema_revision": ", ".join(sorted(applied)) or None,
        "expected_schema_revision": ", ".join(sorted(expected)) or None,
        "timezones": "ok" if timezones_ok else "missing",
        # "meaning and keywords" with the embedding model, else "keywords only".
        "document_search": (
            "meaning and keywords" if get_embedder() is not None else "keywords only"
        ),
        "environment": settings.environment,
        "auth_required": settings.auth_required,
        **counters,
    }


def _operator(request: Request, db) -> bool:
    """Whether the caller may see the full readiness detail.

    Everyone, when authentication is off (a local development server). With it
    on, only a signed-in account listed in ADMIN_ACCOUNTS whose session is
    current — the same people who can open the dashboard.
    """
    if not settings.auth_required:
        return True
    claims = session_claims(request.cookies.get(COOKIE, ""))
    if not claims or claims[0] not in settings.admin_accounts:
        return False
    account = get_by_id(db, claims[0])
    return account is not None and (account.session_epoch or 0) == claims[1]


def _erroring(counters: dict) -> bool:
    """Sustained trouble only: a spent daily quota, a model failing request
    after request, or a run of recent unhandled errors. A single provider
    timeout is counted in ``provider.failure_streaks`` and left to the person
    who saw it to retry; the database and schema checks sit outside this."""
    last = counters.get("last_error")
    recent = bool(
        last
        and last.get("at")
        and (datetime.now(UTC) - datetime.fromisoformat(last["at"])).total_seconds() < 900
    )
    return bool(
        counters["provider"].get("blocked_models") or counters["provider"].get("failed_models")
    ) or (counters["unhandled_errors"] >= settings.alert_error_threshold and recent)
