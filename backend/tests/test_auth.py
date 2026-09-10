import hashlib
import time

import pytest

from app.core.auth import sign_session
from app.core.config import Settings, settings


def enable(monkeypatch, users):
    keys = {u.id: hashlib.sha256(k.encode()).hexdigest() for u, k in users}
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(settings, "auth_access_keys", keys)


def test_authentication_blocks_impersonation_and_cross_account_reads(
    client, make_user, monkeypatch
):
    alice, bob = make_user("Alice"), make_user("Bob")
    enable(monkeypatch, [(alice, "a" * 40), (bob, "b" * 40)])
    origin = {"Origin": settings.frontend_url}
    assert client.get("/api/memory/shared", headers={"X-User-Id": alice.id}).status_code == 401
    assert (
        client.post(
            "/api/team/ask",
            json={"question": "hello", "agent_ids": ["study"]},
            headers={**origin, "X-User-Id": alice.id},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/agents/study/chat/stream",
            json={"message": "hello"},
            headers={**origin, "X-User-Id": alice.id},
        ).status_code
        == 401
    )
    assert (
        client.post("/api/auth/login", json={"access_key": "x" * 40}, headers=origin).status_code
        == 401
    )
    assert (
        client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin).status_code
        == 200
    )
    goal = client.post("/api/goals", json={"title": "Alice private"}, headers=origin).json()
    convo = client.post("/api/conversations", json={"agent_id": "study"}, headers=origin).json()
    assert client.get("/api/users/me", headers={"X-User-Id": bob.id}).json()["id"] == alice.id
    assert (
        client.post(
            "/api/goals", json={"title": "csrf"}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    client.post("/api/auth/logout")
    assert client.get("/api/goals").status_code == 401
    client.post("/api/auth/login", json={"access_key": "b" * 40}, headers=origin)
    assert client.get("/api/goals").json() == []
    assert (
        client.patch(
            "/api/goals/" + goal["id"], json={"status": "done"}, headers=origin
        ).status_code
        == 404
    )
    assert client.get("/api/conversations/" + convo["id"]).status_code == 404
    r = client.post(
        "/api/agents/study/chat",
        json={"message": "show it", "conversation_id": convo["id"]},
        headers=origin,
    )
    assert r.status_code == 400


def test_sessions_expire_and_revoke(client, make_user, monkeypatch):
    u = make_user("Alice")
    enable(monkeypatch, [(u, "a" * 40)])
    from app.core.auth import session_user

    token = sign_session(u.id)
    assert session_user(token) == u.id
    assert session_user(token + "x") is None
    monkeypatch.setattr(time, "time", lambda: 9999999999)
    assert session_user(token) is None


def test_production_fails_closed():
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="production")


def test_ask_my_team_rejects_anonymous_and_forged_callers(client, make_user, monkeypatch):
    """Ask My Team reaches every specialist at once, so it is the widest blast radius.

    It was the last route to be put behind auth; this pins both halves down —
    no session means no answer, and a session cannot be redirected at someone
    else's account with a header.
    """
    alice, bob = make_user("Alice"), make_user("Bob")
    enable(monkeypatch, [(alice, "a" * 40), (bob, "b" * 40)])
    origin = {"Origin": settings.frontend_url}
    ask = {"question": "what should I do next?", "agent_ids": ["study", "career"]}

    assert client.post("/api/team/ask", json=ask, headers=origin).status_code == 401
    assert (
        client.post("/api/team/ask", json=ask, headers={**origin, "X-User-Id": bob.id}).status_code
        == 401
    )
    assert client.post("/api/team/ask", json=ask).status_code == 403  # no origin

    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    # Signed in as Alice, but asking on Bob's behalf: the header must be ignored.
    assert (
        client.post("/api/team/ask", json=ask, headers={**origin, "X-User-Id": bob.id}).status_code
        == 200
    )
    mine = client.get("/api/conversations").json()
    assert mine and {c["agent_id"] for c in mine} == {"study", "career"}

    # Bob's account must not have gained the conversations Alice's request created.
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"access_key": "b" * 40}, headers=origin)
    assert client.get("/api/conversations").json() == []
    assert client.post("/api/team/ask", json={**ask, "agent_ids": ["nope"]}).status_code == 403


#: Routes that are deliberately reachable without a session. Everything else
#: touches one person's data and must refuse an anonymous caller.
PUBLIC_ROUTES = {
    ("GET", "/api/health"),
    ("GET", "/api/agents"),
    ("GET", "/api/agents/{agent_id}"),
    ("GET", "/api/auth/status"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
}
_SAMPLE_BODY = {
    "/api/goals": {"title": "x"},
    "/api/memory/shared": {"category": "context", "key": "k", "value": "v"},
    "/api/memory/agent": {"agent_id": "study", "category": "context", "key": "k", "value": "v"},
    "/api/conversations": {"agent_id": "study"},
    "/api/team/ask": {"question": "hi", "agent_ids": ["study"]},
    "/api/users/me": {"display_name": "x"},
}


def test_every_personal_data_route_refuses_an_anonymous_caller(client, make_user, monkeypatch):
    """Walk the real route table so a new endpoint cannot quietly skip auth."""
    from app.main import app

    enable(monkeypatch, [(make_user("Alice"), "a" * 40)])
    origin = {"Origin": settings.frontend_url}
    checked = 0

    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api"):
            continue
        for method in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
            if (method, path) in PUBLIC_ROUTES:
                continue
            url = path.replace("{agent_id}", "study")
            for placeholder in ("{goal_id}", "{memory_id}", "{conversation_id}"):
                url = url.replace(placeholder, "does-not-exist")
            response = client.request(method, url, json=_SAMPLE_BODY.get(path), headers=origin)
            assert response.status_code == 401, f"{method} {path} returned {response.status_code}"
            checked += 1

    assert checked >= 15, f"only {checked} routes checked — the sweep found too little"


def test_revoking_an_access_key_invalidates_an_existing_session(client, make_user, monkeypatch):
    """Removing someone's key is the revocation mechanism, so it must kill live sessions."""
    alice, bob = make_user("Alice"), make_user("Bob")
    enable(monkeypatch, [(alice, "a" * 40), (bob, "b" * 40)])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    assert client.get("/api/goals").status_code == 200

    monkeypatch.setattr(
        settings,
        "auth_access_keys",
        {bob.id: hashlib.sha256(("b" * 40).encode()).hexdigest()},
    )
    assert client.get("/api/goals").status_code == 401


def test_a_session_signed_with_another_secret_is_rejected(make_user, monkeypatch):
    """A leaked cookie from a different deployment must not authenticate here."""
    from app.core.auth import session_user

    alice = make_user("Alice")
    enable(monkeypatch, [(alice, "a" * 40)])
    token = sign_session(alice.id)
    assert session_user(token) == alice.id

    monkeypatch.setattr(settings, "auth_secret", "different" * 5)
    assert session_user(token) is None


def test_login_rejects_a_valid_key_for_a_deleted_account(client, make_user, monkeypatch):
    alice = make_user("Alice")
    enable(monkeypatch, [(alice, "a" * 40)])
    monkeypatch.setattr(
        settings,
        "auth_access_keys",
        {"ghost-user-id": hashlib.sha256(("g" * 40).encode()).hexdigest()},
    )
    response = client.post(
        "/api/auth/login",
        json={"access_key": "g" * 40},
        headers={"Origin": settings.frontend_url},
    )
    assert response.status_code == 401


def test_signing_out_everywhere_revokes_only_this_account(client, make_user, monkeypatch, db):
    """A lost device must not force everyone else to sign in again."""
    alice, bob = make_user("Alice"), make_user("Bob")
    enable(monkeypatch, [(alice, "a" * 40), (bob, "b" * 40)])
    origin = {"Origin": settings.frontend_url}

    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    alice_cookie = dict(client.cookies)
    assert client.get("/api/goals").status_code == 200

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"access_key": "b" * 40}, headers=origin)
    bob_cookie = dict(client.cookies)

    # Alice signs out everywhere from one device.
    client.cookies.clear()
    client.cookies.update(alice_cookie)
    assert client.post("/api/auth/sign-out-everywhere", headers=origin).status_code == 200

    # Her other device's cookie is spent...
    client.cookies.clear()
    client.cookies.update(alice_cookie)
    assert client.get("/api/goals").status_code == 401
    assert (
        client.post("/api/agents/study/chat", json={"message": "hi"}, headers=origin).status_code
        == 401
    )
    assert (
        client.post(
            "/api/team/ask",
            json={"question": "hi", "agent_ids": ["study"]},
            headers=origin,
        ).status_code
        == 401
    )

    # ...and Bob is untouched.
    client.cookies.clear()
    client.cookies.update(bob_cookie)
    assert client.get("/api/goals").status_code == 200


def test_signing_in_again_after_revocation_works(client, make_user, monkeypatch):
    alice = make_user("Alice")
    enable(monkeypatch, [(alice, "a" * 40)])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    client.post("/api/auth/sign-out-everywhere", headers=origin)
    client.cookies.clear()
    assert (
        client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin).status_code
        == 200
    )
    assert client.get("/api/goals").status_code == 200
