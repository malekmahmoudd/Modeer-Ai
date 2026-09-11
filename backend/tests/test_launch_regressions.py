import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy.exc import StatementError

from app.core import observability as obs
from app.core.alerts import Throttle
from app.core.config import settings


def test_export_after_daily_briefing(client):
    briefing = client.get("/api/briefings/today").json()
    exported = client.get("/api/users/me/export")
    assert exported.status_code == 200
    assert exported.json()["briefings"][0]["generated_for_date"] == briefing["generated_for_date"]


def test_private_exception_data_never_logged(caplog, monkeypatch):
    monkeypatch.setattr(obs, "health", obs.Health())
    request = Request({"type": "http", "method": "POST", "path": "/private-marker", "headers": []})
    exc = StatementError(
        "private-message",
        "INSERT private-sql",
        {"value": "private-memory"},
        ValueError("private-cause"),
    )
    with caplog.at_level(logging.ERROR):
        result = asyncio.run(obs.unhandled(request, exc))
    assert result.status_code == 500
    assert "StatementError" in caplog.text
    assert all(
        x not in caplog.text
        for x in [
            "private-message",
            "private-sql",
            "private-memory",
            "private-cause",
            "private-marker",
        ]
    )
    record = logging.LogRecord(
        "uvicorn.error", 40, "server", 1, "failure %s", (exc,), (type(exc), exc, None)
    )
    obs.SafeServerException().filter(record)
    assert "private" not in logging.Formatter().format(record)


def test_repeated_errors_share_cooldown(monkeypatch):
    monkeypatch.setattr(obs, "health", obs.Health())
    monkeypatch.setattr(settings, "alert_error_threshold", 3)
    throttle = Throttle()
    sent = []

    def notify(*args, **kwargs):
        if throttle.allow(kwargs["key"], now=100):
            sent.append(kwargs["key"])

    monkeypatch.setattr(obs, "notify", notify)
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    for _ in range(12):
        asyncio.run(obs.unhandled(request, RuntimeError("private")))
    assert sent == ["unhandled-errors"]


def test_readiness_tracks_quota_and_recovers(client, monkeypatch):
    monkeypatch.setattr(obs, "health", obs.Health())
    from app.api.routes import health as route

    monkeypatch.setattr(route, "health_counters", obs.health)
    assert client.get("/api/health/detail").status_code == 200
    obs.record_rate_limit(300, "model-a")
    assert client.get("/api/health/detail").status_code == 503
    obs.record_provider_success("model-b")
    assert client.get("/api/health/detail").status_code == 503
    obs.record_provider_success("model-a")
    assert client.get("/api/health/detail").status_code == 200
    obs.health.provider_blocked_until["model-a"] = time.time() - 1
    assert client.get("/api/health/detail").status_code == 200
    obs.record_provider_failure("model-a")
    assert client.get("/api/health/detail").status_code == 503
    obs.record_provider_success("model-a")
    assert client.get("/api/health/detail").status_code == 200
    obs.health.unhandled_errors = 6
    obs.health.last_error_id = "123abc"
    obs.health.last_error_at = datetime.now(UTC)
    assert client.get("/api/health/detail").status_code == 503
    obs.health.last_error_at -= timedelta(minutes=16)
    assert client.get("/api/health/detail").status_code == 200


def test_alert_delivery_tries_other_channel_and_reports_failure(monkeypatch):
    from app.core import alerts

    monkeypatch.setattr(settings, "alert_webhook_url", "https://example.invalid/hook")
    monkeypatch.setattr(settings, "alert_telegram_bot_token", "test-only")
    monkeypatch.setattr(settings, "alert_telegram_chat_id", "test-only")
    calls = []

    async def post(client, url, payload):
        calls.append(url)
        if "example.invalid" in url:
            raise TimeoutError("private webhook")
        return True

    monkeypatch.setattr(alerts, "_post", post)
    assert asyncio.run(alerts._deliver("test")) is True
    assert len(calls) == 2

    async def failed(*args):
        return False

    monkeypatch.setattr(alerts, "_post", failed)
    assert asyncio.run(alerts._deliver("test")) is False


def test_operator_test_alert_only_reports_confirmed_acceptance(client, user, monkeypatch):
    from app.api.routes import admin

    monkeypatch.setattr(settings, "admin_accounts", [user.id])
    monkeypatch.setattr(admin, "alerts_enabled", lambda: True)

    async def failed(*args):
        return False

    monkeypatch.setattr(admin, "_deliver", failed)
    assert (
        client.post(
            "/api/admin/test-alert", headers={"Origin": "http://localhost:3000"}
        ).status_code
        == 502
    )

    async def accepted(*args):
        return True

    monkeypatch.setattr(admin, "_deliver", accepted)
    assert client.post(
        "/api/admin/test-alert", headers={"Origin": "http://localhost:3000"}
    ).json() == {"sent": True}


def test_preferences_reach_specialists_in_live_and_eval_context(db, user):
    from app.agents.context import build_context
    from app.agents.registry import require_agent
    from app.db.models import AgentMemory, SharedMemory
    from app.memory.service import context_for_agent

    preference = SharedMemory(
        user_id=user.id, category="preferences", key="ecosystem", value="iPhone and Apple Watch"
    )
    unrelated = SharedMemory(
        user_id=user.id, category="education", key="institution", value="Unrelated university"
    )
    private = AgentMemory(
        user_id=user.id,
        agent_id="career",
        key="private_note",
        value="Private career fact",
    )
    db.add_all([preference, unrelated, private])
    db.commit()
    agent = require_agent("shopping")
    shared, notes = context_for_agent(db, user.id, agent)
    assert preference in shared and unrelated not in shared
    assert not notes
    packet = build_context(
        agent=agent,
        user=user,
        shared=[preference, unrelated],
        agent_memory=notes,
        goals=[],
        history=[],
        user_message="Recommend a phone",
    )
    assert "iPhone and Apple Watch" in packet.system
    assert "Unrelated university" not in packet.system
    assert "Private career fact" not in packet.system
