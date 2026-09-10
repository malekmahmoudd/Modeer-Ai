"""Alerting and the operator dashboard.

An alerting path nobody has exercised is a guess. These tests cover the three
properties that make it trustworthy rather than decorative: it is silent unless
configured, it never repeats itself into a flood, and it never carries anything
the user wrote.
"""

from __future__ import annotations

import hashlib

import pytest

from app.core import alerts
from app.core.config import settings
from app.core.observability import health


@pytest.fixture(autouse=True)
def _quiet_alerts(monkeypatch):
    """No test may reach the network; capture what would have been sent."""
    sent: list[str] = []

    async def fake_deliver(text: str) -> None:
        sent.append(text)

    monkeypatch.setattr(alerts, "_deliver", fake_deliver)
    monkeypatch.setattr(alerts, "throttle", alerts.Throttle())
    return sent


def _configure_channel(monkeypatch):
    monkeypatch.setattr(settings, "alert_webhook_url", "https://example.invalid/hook")


# --- the alerting contract ---------------------------------------------------


def test_alerting_is_silent_when_no_channel_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "alert_webhook_url", "")
    monkeypatch.setattr(settings, "alert_telegram_bot_token", "")
    assert alerts.enabled() is False
    # Must not raise, and must not try to send.
    alerts.notify("something", "detail")


def test_the_same_problem_alerts_once_per_window(monkeypatch):
    _configure_channel(monkeypatch)
    throttle = alerts.Throttle()

    assert throttle.allow("provider-quota", now=0) is True
    assert throttle.allow("provider-quota", now=10) is False
    assert throttle.allow("provider-quota", now=alerts.THROTTLE_SECONDS + 1) is True
    # A different problem is never suppressed by an unrelated one.
    assert throttle.allow("database-down", now=10) is True


def test_alert_text_carries_no_user_content(monkeypatch):
    """Alerts land in a chat app; a conversation must never reach one."""
    _configure_channel(monkeypatch)
    text = alerts._format(
        "Unhandled errors",
        "3 since start. Latest incident ab12cd (ValueError) on /api/agents/{agent_id}/chat.",
        alerts.Severity.CRITICAL,
    )
    assert "ab12cd" in text
    assert "{agent_id}" in text, "the route template, not a real conversation id"
    assert settings.environment in text


# --- provider quota ----------------------------------------------------------


def test_a_long_retry_after_is_treated_as_the_daily_quota(monkeypatch, _quiet_alerts):
    from app.core.observability import DAILY_QUOTA_RETRY_SECONDS, record_rate_limit

    _configure_channel(monkeypatch)
    monkeypatch.setattr(health, "provider_rate_limits", 0)
    monkeypatch.setattr(health, "provider_quota_exhausted_at", None)

    # A per-minute throttle is routine: counted, not alerted.
    record_rate_limit(30.0)
    assert health.provider_rate_limits == 1
    assert health.provider_quota_exhausted_at is None

    # A wait this long means nobody can use the product until it refills.
    record_rate_limit(DAILY_QUOTA_RETRY_SECONDS + 60)
    assert health.provider_rate_limits == 2
    assert health.provider_quota_exhausted_at is not None


# --- the dashboard -----------------------------------------------------------


def _sign_in(client, monkeypatch, user, key="a" * 40):
    keys = {user.id: hashlib.sha256(key.encode()).hexdigest()}
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(settings, "auth_access_keys", keys)
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": key}, headers=origin)
    return origin


def test_dashboard_is_closed_when_no_admin_is_configured(client, make_user, monkeypatch):
    """Empty ADMIN_ACCOUNTS must mean nobody, not everybody."""
    alice = make_user("Alice")
    _sign_in(client, monkeypatch, alice)
    monkeypatch.setattr(settings, "admin_accounts", [])
    assert client.get("/api/admin/dashboard").status_code == 404
    assert client.get("/api/admin/metrics").status_code == 404


def test_a_non_admin_account_gets_404_not_403(client, make_user, monkeypatch):
    """403 would confirm the page exists; an operator page should not."""
    alice, bob = make_user("Alice"), make_user("Bob")
    _sign_in(client, monkeypatch, alice)
    monkeypatch.setattr(settings, "admin_accounts", [bob.id])
    assert client.get("/api/admin/dashboard").status_code == 404


def test_an_admin_sees_the_dashboard_and_its_metrics(client, make_user, monkeypatch):
    alice = make_user("Alice")
    origin = _sign_in(client, monkeypatch, alice)
    monkeypatch.setattr(settings, "admin_accounts", [alice.id])

    # Spend some budget so the usage table has a row.
    client.post("/api/agents/study/chat", json={"message": "hello"}, headers=origin)

    page = client.get("/api/admin/dashboard")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "Modeer operations" in page.text
    assert "Account usage today" in page.text

    data = client.get("/api/admin/metrics").json()
    assert data["requests"] >= 1
    assert "provider" in data
    assert data["accounts_today"], "no usage recorded for the account that just chatted"
    assert data["accounts_today"][0]["account"] == "Alice"
    assert data["tokens_today"] > 0


def test_test_alert_refuses_when_nothing_is_configured(client, make_user, monkeypatch):
    alice = make_user("Alice")
    origin = _sign_in(client, monkeypatch, alice)
    monkeypatch.setattr(settings, "admin_accounts", [alice.id])
    monkeypatch.setattr(settings, "alert_webhook_url", "")
    monkeypatch.setattr(settings, "alert_telegram_bot_token", "")
    response = client.post("/api/admin/test-alert", headers=origin)
    assert response.status_code == 400
    assert "no alert channel" in response.json()["detail"].lower()
