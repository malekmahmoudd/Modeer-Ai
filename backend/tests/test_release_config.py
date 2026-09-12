"""What the initial release switches off, checked the way it will actually run.

The suite runs with TEAM_ENABLED=true (see conftest.py) so the Ask My Team
implementation stays tested. These tests pin the shipped defaults instead.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.main import app

BACKEND = Path(__file__).resolve().parents[1]
ASK = {"question": "How should I plan my week?", "agent_ids": ["study"]}


# --- Ask My Team ----------------------------------------------------------------


def test_team_ships_disabled():
    assert Settings.model_fields["team_enabled"].default is False


def test_disabled_team_is_not_found_for_a_signed_in_caller(client, monkeypatch):
    monkeypatch.setattr(settings, "team_enabled", False)
    response = client.post("/api/team/ask", json=ASK)
    assert response.status_code == 404
    assert response.json()["detail"] == "Ask My Team is not available"


def test_disabled_team_still_asks_anonymous_callers_to_sign_in(client, monkeypatch, make_user):
    """Authentication answers first, so the 404 tells an outsider nothing."""
    alice = make_user("Alice")
    monkeypatch.setattr(settings, "team_enabled", False)
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(
        settings, "auth_access_keys", {alice.id: hashlib.sha256(b"a" * 40).hexdigest()}
    )
    response = client.post("/api/team/ask", json=ASK, headers={"Origin": settings.frontend_url})
    assert response.status_code == 401


def test_positive_control_enabled_team_answers(client, monkeypatch):
    monkeypatch.setattr(settings, "team_enabled", True)
    response = client.post("/api/team/ask", json=ASK)
    assert response.status_code == 200, response.text
    assert [t["agent_id"] for t in response.json()["takes"]] == ["study"]


# --- API docs -------------------------------------------------------------------


def _production_app_urls() -> dict:
    """Import the real app in a fresh interpreter configured for production."""
    env = {
        **os.environ,
        "ENVIRONMENT": "production",
        "DEBUG": "false",
        "AUTH_REQUIRED": "true",
        "AUTH_SECRET": "s" * 40,
        "AUTH_ACCESS_KEYS": json.dumps({"someone": hashlib.sha256(b"k" * 40).hexdigest()}),
        "FRONTEND_URL": "https://modeer.example",
        # Production refuses the mock model, so the probe needs a real one.
        "LLM_PROVIDER": "groq",
        "LLM_API_KEY": "not-a-real-key",
    }
    probe = (
        "import json; from app.main import app; "
        "print(json.dumps({'docs': app.docs_url, 'redoc': app.redoc_url, "
        "'openapi': app.openapi_url}))"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_api_docs_are_off_in_production():
    assert _production_app_urls() == {"docs": None, "redoc": None, "openapi": None}


def test_public_readiness_says_only_what_an_uptime_check_needs(client, make_user, monkeypatch):
    """With authentication on, an anonymous caller learns up or down — not model
    names, counters, incident ids or error types. An admin still sees it all."""
    alice = make_user("Alice")
    key = "a" * 40
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(
        settings, "auth_access_keys", {alice.id: hashlib.sha256(key.encode()).hexdigest()}
    )
    anonymous = client.get("/api/health/detail").json()
    assert set(anonymous) == {"status", "database", "schema_current"}

    monkeypatch.setattr(settings, "admin_accounts", [alice.id])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": key}, headers=origin)
    admin = client.get("/api/health/detail").json()
    assert {"provider", "unhandled_errors", "schema_revision"} <= set(admin)


def test_sync_chat_route_is_not_served_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    assert client.post("/api/agents/study/chat", json={"message": "hello"}).status_code == 404
    liveness = client.get("/api/health").json()
    assert set(liveness) == {"status", "database"}, "production liveness names the model"


def test_production_refuses_the_offline_preview_model():
    """Without this, a missing LLM_PROVIDER serves canned replies to invitees
    while every health check reports ok."""
    production = {
        "environment": "production",
        "debug": False,
        "auth_required": True,
        "auth_secret": "s" * 40,
        "auth_access_keys": {"someone": "a" * 64},
        "frontend_url": "https://modeer.example",
    }
    with pytest.raises(ValidationError, match="LLM_PROVIDER"):
        Settings(**production, llm_provider="mock", llm_api_key="x")
    with pytest.raises(ValidationError, match="LLM_API_KEY"):
        Settings(**production, llm_provider="groq", llm_api_key="")
    assert Settings(**production, llm_provider="groq", llm_api_key="x").llm_provider == "groq"


def test_positive_control_api_docs_are_on_in_development(client):
    assert settings.environment != "production"
    assert app.docs_url == "/docs"
    assert client.get("/openapi.json").status_code == 200
