from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Configure the environment BEFORE any app import (settings is a cached singleton).
_TMP_DB = Path(tempfile.gettempdir()) / "modeer_test.db"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_TMP_DB.as_posix()}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["MEMORY_STORE_SENSITIVE"] = "false"
os.environ["MEMORY_MIN_CONFIDENCE"] = "0.55"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.agents.sync import sync_agents  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.users.service import get_or_create_demo_user  # noqa: E402

_WIPE_TABLES = [
    "briefings",
    "goals",
    "agent_memories",
    "shared_memories",
    "messages",
    "conversations",
    "users",
]


@pytest.fixture(scope="session", autouse=True)
def _database():
    if _TMP_DB.exists():
        _TMP_DB.unlink()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        sync_agents(db)
        db.commit()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()  # release the SQLite file handle before unlinking (Windows)
    try:
        if _TMP_DB.exists():
            _TMP_DB.unlink()
    except PermissionError:
        pass


@pytest.fixture(autouse=True)
def _clean_between_tests():
    yield
    with engine.begin() as conn:
        for table in _WIPE_TABLES:
            conn.execute(text(f"DELETE FROM {table}"))


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user(db):
    u = get_or_create_demo_user(db)
    db.commit()
    return u


@pytest.fixture
def make_user(db):
    from app.db.models import User

    created: list[str] = []

    def _make(name: str, email: str | None = None) -> User:
        u = User(display_name=name, email=email or f"{name.lower()}@test.local")
        db.add(u)
        db.commit()
        created.append(u.id)
        return u

    return _make
