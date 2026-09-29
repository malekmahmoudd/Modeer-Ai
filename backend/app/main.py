from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agents.sync import sync_agents
from app.api import api_router
from app.conversations.service import purge_incognito
from app.core import sessions as devices
from app.core.config import settings
from app.core.lang import request_locale, translate_detail
from app.core.observability import install as install_observability
from app.db.base import Base
from app.db.session import SessionLocal, engine

logging.basicConfig(level=logging.INFO)
# HTTP client INFO/DEBUG logs contain full URLs, including webhook credentials.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("modeer")

#: How often due reminders are looked for (each person gets one a day).
PUSH_EVERY_SECONDS = 600

#: How often expired incognito chats are swept away, for everyone.
INCOGNITO_SWEEP_SECONDS = 3600


def sweep_incognito() -> int:
    """Delete every incognito chat past its 24 hours. Also done per account
    whenever someone lists their chats; this catches people who never return.
    Device records that ended over 30 days ago, and quick-note receipts older
    than a day, go in the same pass."""
    from app.tracking.service import sweep_capture_receipts

    with SessionLocal() as db:
        removed = purge_incognito(db)
        devices.sweep(db)
        sweep_capture_receipts(db)
        db.commit()
    return removed


async def _push_forever() -> None:
    """Send each person's daily reminder when their hour comes."""
    from app.push.service import send_due

    while True:
        await asyncio.sleep(PUSH_EVERY_SECONDS)
        if not settings.push_enabled:
            continue
        try:
            with SessionLocal() as db:
                sent = await send_due(db)
            if sent:
                logger.info("Sent %d reminders", sent)
        except Exception as exc:  # noqa: BLE001 - try again next round
            logger.warning("Reminders failed: %s", type(exc).__name__)


async def _sweep_forever() -> None:
    while True:
        try:
            removed = await asyncio.to_thread(sweep_incognito)
            if removed:
                logger.info("Removed %d expired incognito chats", removed)
        except Exception as exc:  # noqa: BLE001 - try again next hour
            logger.warning("Incognito sweep failed: %s", type(exc).__name__)
        await asyncio.sleep(INCOGNITO_SWEEP_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Zero-config path: auto-create the schema on SQLite. For PostgreSQL, run
    # `alembic upgrade head` first — this block then just refreshes agent rows.
    if settings.is_sqlite:
        Base.metadata.create_all(bind=engine)
    try:
        with SessionLocal() as db:
            n = sync_agents(db)
            db.commit()
            logger.info("Synced %d agents into the registry table", n)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Agent sync skipped (has the database been migrated?): %s", type(exc).__name__
        )
    sweeper = asyncio.create_task(_sweep_forever())
    pusher = asyncio.create_task(_push_forever())
    try:
        yield
    finally:
        for task in (sweeper, pusher):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def api_docs(environment: str) -> dict:
    """Interactive docs are a development aid. In production they would publish
    every route and schema to anyone who can reach the API, so they are off —
    whatever the proxy in front happens to route."""
    if environment == "production":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


async def _translated_http_error(request: Request, exc: StarletteHTTPException):
    """The app's own error messages, in the person's language (app.core.lang)."""
    detail = translate_detail(exc.detail, request_locale(request))
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=exc.headers)


async def _translated_validation_error(request: Request, exc: RequestValidationError):
    detail = translate_detail(jsonable_encoder(exc.errors()), request_locale(request))
    return JSONResponse({"detail": detail}, status_code=422)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Fareeq: Leo, your personal manager, plus a shared-context specialist team.",
    lifespan=lifespan,
    **api_docs(settings.environment),
)

install_observability(app)
app.add_exception_handler(StarletteHTTPException, _translated_http_error)
app.add_exception_handler(RequestValidationError, _translated_validation_error)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "docs": app.docs_url, "api": "/api"}
