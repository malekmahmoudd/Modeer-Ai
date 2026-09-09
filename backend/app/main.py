from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.sync import sync_agents
from app.api import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("modeer")


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
            "Agent sync skipped (has the database been migrated?): %s", exc
        )
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Personal AI assistant (Modeer) plus a shared-context specialist team.",
    lifespan=lifespan,
)

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
    return {"service": settings.app_name, "docs": "/docs", "api": "/api"}
