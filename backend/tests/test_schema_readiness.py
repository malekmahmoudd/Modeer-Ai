"""Readiness must track the schema this build expects, not a written-down number.

It used to compare against a literal "0003". The next migration would have left
production reporting degraded forever on a perfectly healthy app, and a watchdog
that alerts on nothing teaches the person holding it to stop reading alerts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text

from app.api.routes import health as health_route
from app.core.config import settings
from app.db.session import engine

_VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"


@pytest.fixture
def stamp(monkeypatch):
    """Give the test database an alembic_version table and set its contents.

    The test database is built with create_all, so it has no alembic_version
    until we make one. Provider and error counters are shared across the whole
    suite; neutralise them so these tests measure the schema check alone.
    """
    monkeypatch.setattr(health_route, "_erroring", lambda counters: False)
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        )

    def _stamp(*revisions: str) -> None:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM alembic_version"))
            for revision in revisions:
                conn.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": revision})

    yield _stamp
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


def _in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")


def test_expected_revision_is_the_latest_migration_actually_shipped():
    """Independent of Alembic: the head is the revision nobody else revises."""
    revisions, revised = set(), set()
    for script in _VERSIONS.glob("*.py"):
        body = script.read_text(encoding="utf-8")
        if match := re.search(r'^revision\s*=\s*["\']([^"\']+)', body, re.M):
            revisions.add(match.group(1))
        if match := re.search(r'^down_revision\s*=\s*["\']([^"\']+)', body, re.M):
            revised.add(match.group(1))
    assert health_route.expected_schema_revisions() == frozenset(revisions - revised)


def test_production_is_ready_when_the_schema_is_current(client, stamp, monkeypatch):
    _in_production(monkeypatch)
    (head,) = health_route.expected_schema_revisions()
    stamp(head)

    response = client.get("/api/health/detail")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_current"] is True
    assert body["schema_revision"] == body["expected_schema_revision"] == head


def test_a_new_migration_is_ready_once_applied(client, stamp, monkeypatch):
    """The exact case the literal broke: ship 0004, migrate to 0004, stay green."""
    _in_production(monkeypatch)
    monkeypatch.setattr(health_route, "expected_schema_revisions", lambda: frozenset({"0004"}))
    stamp("0004")
    assert client.get("/api/health/detail").status_code == 200


def test_an_unapplied_migration_reports_degraded(client, stamp, monkeypatch):
    """Built with 0004 but the database is still at 0003: the stale-image failure."""
    _in_production(monkeypatch)
    monkeypatch.setattr(health_route, "expected_schema_revisions", lambda: frozenset({"0004"}))
    stamp("0003")

    response = client.get("/api/health/detail")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["schema_current"] is False
    assert body["schema_revision"] == "0003"
    assert body["expected_schema_revision"] == "0004"


def test_unreadable_migration_scripts_fail_closed_in_production(client, stamp, monkeypatch):
    """A process that cannot tell which schema it expects cannot claim to be on it."""
    _in_production(monkeypatch)
    monkeypatch.setattr(health_route, "expected_schema_revisions", lambda: frozenset())
    stamp("0003")
    assert client.get("/api/health/detail").status_code == 503


def test_branched_history_needs_every_head_applied(client, stamp, monkeypatch):
    _in_production(monkeypatch)
    monkeypatch.setattr(
        health_route, "expected_schema_revisions", lambda: frozenset({"0004a", "0004b"})
    )
    stamp("0004a")
    assert client.get("/api/health/detail").status_code == 503
    stamp("0004a", "0004b")
    assert client.get("/api/health/detail").status_code == 200


def test_outside_production_a_schema_mismatch_does_not_degrade(client, stamp, monkeypatch):
    """Development SQLite databases are built by create_all and never stamped."""
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(health_route, "expected_schema_revisions", lambda: frozenset({"0004"}))
    stamp("0001")
    assert client.get("/api/health/detail").status_code == 200
