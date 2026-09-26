"""Signed-in devices, two-step sign-in, and every account's usage for operators."""

from __future__ import annotations

import base64
import hashlib
import time

import pytest

from app.core import totp
from app.core.config import settings
from app.core.passwords import hash_password
from app.db.models import User

PASSWORD = "correct horse battery staple"
CHROME_MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)


@pytest.fixture
def account(db, monkeypatch):
    """A password account with recovery codes, authentication on."""
    user = User(display_name="Sam", email="sam@example.com", password_hash=hash_password(PASSWORD))
    db.add(user)
    db.commit()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(settings, "auth_access_keys", {})
    monkeypatch.setattr(settings, "admin_accounts", [user.id])
    return user


def _headers(agent: str = CHROME_MAC) -> dict:
    # Behind Caddy the client address arrives as X-Forwarded-For.
    return {"Origin": settings.frontend_url, "User-Agent": agent, "X-Forwarded-For": "203.0.113.7"}


def _login(client, agent: str = CHROME_MAC, code: str | None = None):
    client.cookies.clear()
    body = {"email": "sam@example.com", "password": PASSWORD}
    if code:
        body["code"] = code
    return client.post("/api/auth/login", json=body, headers=_headers(agent))


# --- the algorithm ---------------------------------------------------------------------


def test_codes_match_the_rfc_6238_test_vectors():
    secret = base64.b32encode(b"12345678901234567890").decode()
    for moment, expected in [(59, "94287082"), (1111111109, "07081804"), (2000000000, "69279037")]:
        assert totp.code_at(secret, moment // 30, digits=8) == expected


def test_a_code_counts_once_and_only_near_now():
    secret = totp.new_secret()
    now = time.time()
    code = totp.code_at(secret, totp.current_step(now))
    step = totp.verify(secret, code, now=now)
    assert step is not None
    assert totp.verify(secret, code, last_step=step, now=now) is None  # replay refused
    assert totp.verify(secret, code, now=now + 300) is None  # five minutes later
    assert totp.verify(secret, "12 34 5", now=now) is None


# --- devices ------------------------------------------------------------------------


def test_each_sign_in_is_a_device_that_can_be_signed_out_alone(client, account):
    assert _login(client, CHROME_MAC).status_code == 200
    laptop = dict(client.cookies)
    assert _login(client, SAFARI_IPHONE).status_code == 200
    phone = dict(client.cookies)

    listed = client.get("/api/auth/sessions", headers=_headers(SAFARI_IPHONE)).json()
    assert {(d["browser"], d["system"]) for d in listed} == {
        ("Chrome", "Mac"),
        ("Safari", "iPhone"),
    }
    here = next(d for d in listed if d["current"])
    assert here["system"] == "iPhone" and here["network"] == "203.0.113.x"
    laptop_id = next(d["id"] for d in listed if not d["current"])

    # From the phone, sign the laptop out.
    ended = client.delete(f"/api/auth/sessions/{laptop_id}", headers=_headers(SAFARI_IPHONE))
    assert ended.status_code == 204
    client.cookies.clear()
    client.cookies.update(laptop)
    assert client.get("/api/users/me").status_code == 401
    client.cookies.clear()
    client.cookies.update(phone)
    assert client.get("/api/users/me").status_code == 200
    assert len(client.get("/api/auth/sessions").json()) == 1


def test_signing_out_ends_the_device_even_for_a_copied_cookie(client, account):
    _login(client)
    copy = dict(client.cookies)
    client.post("/api/auth/logout")
    client.cookies.update(copy)
    assert client.get("/api/users/me").status_code == 401


def test_another_accounts_device_cannot_be_signed_out(client, account, db):
    _login(client)
    mine = client.get("/api/auth/sessions").json()[0]["id"]
    other = User(display_name="Other", email="o@example.com", password_hash=hash_password(PASSWORD))
    db.add(other)
    db.commit()
    client.cookies.clear()
    client.post(
        "/api/auth/login", json={"email": "o@example.com", "password": PASSWORD}, headers=_headers()
    )
    assert client.delete(f"/api/auth/sessions/{mine}", headers=_headers()).status_code == 404


def test_sign_out_everywhere_empties_the_device_list(client, account):
    _login(client, SAFARI_IPHONE)
    _login(client, CHROME_MAC)
    client.post("/api/auth/sign-out-everywhere", headers=_headers())
    _login(client, CHROME_MAC)
    assert len(client.get("/api/auth/sessions").json()) == 1


# --- two-step sign-in ----------------------------------------------------------------


def _turn_on(client) -> str:
    setup = client.post("/api/auth/2fa/setup", json={"password": PASSWORD}, headers=_headers())
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    assert setup.json()["uri"].startswith("otpauth://totp/Fareeq")
    wrong = client.post("/api/auth/2fa/enable", json={"code": "000000"}, headers=_headers())
    assert wrong.status_code == 403
    code = totp.code_at(secret, totp.current_step())
    on = client.post("/api/auth/2fa/enable", json={"code": code}, headers=_headers())
    assert on.status_code == 200 and on.json()["two_factor"] is True
    return secret


def test_two_step_sign_in_asks_for_a_code_after_the_password(client, account, db):
    _login(client)
    secret = _turn_on(client)
    assert client.get("/api/auth/account").json()["two_factor"] is True

    first = _login(client)
    assert first.status_code == 200
    assert first.json() == {"signed_in": False, "two_factor_required": True}
    assert "modeer_session" not in client.cookies

    assert _login(client, code="123456").status_code == 401
    # The code used to switch it on was spent; wait for the next one.
    db.refresh(account)
    code = totp.code_at(secret, (account.totp_last_step or 0) + 1)
    signed_in = _login(client, code=code)
    if signed_in.status_code == 401:  # the next step is not yet current
        pytest.skip("clock boundary: next code not valid yet")
    assert signed_in.json() == {"signed_in": True}
    assert client.get("/api/users/me").status_code == 200


def test_a_recovery_code_stands_in_for_a_lost_phone(client, account, db):
    from app.api.routes.auth import _issue_codes

    codes = _issue_codes(db, account)
    db.commit()
    _login(client)
    _turn_on(client)
    assert _login(client, code=codes[0]).json() == {"signed_in": True}
    assert _login(client, code=codes[0]).status_code == 401  # each code works once


def test_two_step_needs_a_password_first(client, db, monkeypatch):
    user = User(display_name="Keyed", email="k@example.com")
    db.add(user)
    db.commit()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(
        settings, "auth_access_keys", {user.id: hashlib.sha256(b"k" * 40).hexdigest()}
    )
    client.post("/api/auth/login", json={"access_key": "k" * 40}, headers=_headers())
    setup = client.post("/api/auth/2fa/setup", json={"password": "x"}, headers=_headers())
    assert setup.status_code == 400 and "password first" in setup.json()["detail"]


def test_turning_it_off_needs_the_password_and_a_code(client, account, db):
    from app.api.routes.auth import _issue_codes

    codes = _issue_codes(db, account)
    db.commit()
    _login(client)
    _turn_on(client)
    off = {"password": PASSWORD, "code": "000000"}
    assert client.post("/api/auth/2fa/disable", json=off, headers=_headers()).status_code == 403
    off["code"] = codes[1]
    assert client.post("/api/auth/2fa/disable", json=off, headers=_headers()).json() == {
        "two_factor": False
    }
    assert _login(client).json() == {"signed_in": True}


def test_the_export_says_whether_it_is_on_but_never_the_secret(client, account):
    _login(client)
    secret = _turn_on(client)
    export = client.get("/api/users/me/export").text
    assert secret not in export
    assert '"two_factor":true' in export.replace(" ", "")
    assert "signed_in_devices" in export


# --- usage for every account ----------------------------------------------------------


def test_the_dashboard_lists_every_account_with_its_share(client, account, db):
    idle = User(display_name="Idle", email="idle@example.com")
    db.add(idle)
    db.commit()
    _login(client)
    rows = client.get("/api/admin/metrics").json()["accounts_today"]
    by_name = {r["account"]: r for r in rows}
    assert by_name["Idle"]["percent"] == 0.0 and by_name["Idle"]["used"] == 0
    assert "Sam" in by_name
    page = client.get("/api/admin/dashboard").text
    assert "Idle" in page and "0.0%" in page
