"""Knowing something is wrong, and being able to find out what.

There is no error-tracking service here, so the incident id is the whole
mechanism: the user quotes six characters and the operator greps the log for
them. If the id stops matching, or an internal message starts reaching the
client, that mechanism is gone and nothing says so.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.observability import health
from app.main import app


@pytest.fixture
def tolerant_client():
    """A client that returns the 500 rather than re-raising, as a browser sees it."""
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_health_detail_reports_counters_and_schema(client):
    body = client.get("/api/health/detail").json()
    assert body["status"] in {"ok", "degraded"}
    assert body["database"] == "ok"
    assert body["requests"] >= 1
    assert body["uptime_seconds"] >= 0
    # Present so an operator can see which migration the running process is on.
    assert "schema_revision" in body


def test_an_unhandled_failure_gives_the_user_an_incident_id(tolerant_client):
    @app.get("/api/_test_boom")
    def boom():
        raise RuntimeError("database password is hunter2")

    before = health.unhandled_errors
    response = tolerant_client.get("/api/_test_boom")

    assert response.status_code == 500
    body = response.json()
    assert body["incident"], "no incident id for the user to quote"
    assert body["incident"] == health.last_error_id
    assert health.unhandled_errors == before + 1
    assert health.last_error_type == "RuntimeError"

    # The whole point of a generic message: the exception text may contain
    # anything at all, and it must not reach the client.
    assert "hunter2" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text


def test_streaming_survives_the_access_log_middleware(client):
    """Wrapping every response is the easy way to break SSE; it must not."""
    with client.stream(
        "POST", "/api/agents/study/chat/stream", json={"message": "hello"}
    ) as response:
        assert response.status_code == 200
        events = [line for line in response.iter_lines() if line.startswith("data:")]
    assert len(events) > 3, "the stream arrived as a single buffered chunk or not at all"
