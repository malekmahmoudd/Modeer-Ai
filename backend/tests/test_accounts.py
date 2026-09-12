"""Open signup, password sign-in, recovery codes, and per-person memory consent."""

from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models import RecoveryCode, SharedMemory, User
from app.llm import provider as provider_module
from app.llm.base import LLMProvider

PASSWORD = "correct horse battery"
ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture
def open_signup(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(settings, "auth_access_keys", {})
    monkeypatch.setattr(settings, "signup_enabled", True)
    monkeypatch.setattr(settings, "frontend_url", ORIGIN["Origin"])


def _signup(client, email="alice@example.com", password=PASSWORD, name="Alice"):
    return client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "display_name": name},
        headers=ORIGIN,
    )


def _login(client, email="alice@example.com", password=PASSWORD):
    client.cookies.clear()
    return client.post(
        "/api/auth/login", json={"email": email, "password": password}, headers=ORIGIN
    )


# --- signup ---------------------------------------------------------------------------


def test_signup_is_closed_unless_switched_on(client, open_signup, monkeypatch):
    monkeypatch.setattr(settings, "signup_enabled", False)
    assert _signup(client).status_code == 404
    assert client.get("/api/auth/status").json() == {"required": True, "signup_enabled": False}


def test_signup_creates_a_signed_in_account_with_recovery_codes(client, open_signup, db):
    response = _signup(client)
    assert response.status_code == 201, response.text
    codes = response.json()["recovery_codes"]
    assert len(codes) == 10 and len(set(codes)) == 10
    assert client.get("/api/users/me").json()["display_name"] == "Alice"

    account = db.scalar(select(User).where(User.email == "alice@example.com"))
    assert account.password_hash.startswith("scrypt$")
    assert PASSWORD not in account.password_hash
    stored = db.scalars(select(RecoveryCode.code_hash).where(RecoveryCode.user_id == account.id))
    assert not set(codes) & set(stored), "a recovery code was stored in the clear"
    assert account.memory_auto is True, "automatic memory is on by default"


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ({"email": "a@example.com", "password": "short", "display_name": "A"}, "short password"),
        ({"email": "a@example.com", "password": " " * 12, "display_name": "A"}, "blank password"),
        ({"email": "not-an-email", "password": PASSWORD, "display_name": "A"}, "bad email"),
        ({"email": "a@example.com", "password": PASSWORD, "display_name": "  "}, "blank name"),
    ],
    ids=["short", "blank", "email", "name"],
)
def test_signup_refuses_bad_details(client, open_signup, body, reason):
    assert client.post("/api/auth/signup", json=body, headers=ORIGIN).status_code == 422, reason


def test_one_account_per_email_whatever_the_case(client, open_signup):
    assert _signup(client).status_code == 201
    client.cookies.clear()
    assert _signup(client, email="ALICE@Example.com").status_code == 409


def test_signup_and_recovery_need_the_frontend_origin(client, open_signup):
    body = {"email": "a@example.com", "password": PASSWORD, "display_name": "A"}
    assert client.post("/api/auth/signup", json=body).status_code == 403
    recover = {"email": "a@example.com", "code": "AAAA-BBBB-CCCC", "new_password": PASSWORD}
    assert client.post("/api/auth/recover", json=recover).status_code == 403


def test_signups_from_one_address_are_throttled(client, open_signup):
    statuses = []
    for i in range(7):
        client.cookies.clear()
        statuses.append(_signup(client, email=f"person{i}@example.com").status_code)
    assert statuses[:5] == [201] * 5
    assert statuses[5:] == [429, 429]


# --- signing in -----------------------------------------------------------------------


def test_sign_in_with_email_and_password(client, open_signup):
    _signup(client)
    assert _login(client, email="Alice@Example.com").status_code == 200
    assert client.get("/api/users/me").status_code == 200


def test_a_wrong_password_and_an_unknown_email_look_the_same(client, open_signup):
    _signup(client)
    wrong = _login(client, password="not the password at all")
    unknown = _login(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_password_guessing_is_throttled_per_email(client, open_signup):
    _signup(client)
    statuses = [_login(client, password=f"wrong password {i}").status_code for i in range(12)]
    assert statuses[:10] == [401] * 10
    assert statuses[10:] == [429, 429]
    assert _login(client).status_code == 429, "still locked for the window, even when right"


def test_access_key_accounts_keep_working(client, open_signup, make_user, monkeypatch):
    legacy = make_user("Ken", email="ken@example.com")
    key = "k" * 40
    monkeypatch.setattr(
        settings, "auth_access_keys", {legacy.id: hashlib.sha256(key.encode()).hexdigest()}
    )
    response = client.post("/api/auth/login", json={"access_key": key}, headers=ORIGIN)
    assert response.status_code == 200
    assert client.get("/api/users/me").json()["id"] == legacy.id


def test_a_login_must_use_one_method(client, open_signup):
    both = {"access_key": "k" * 40, "email": "a@example.com", "password": PASSWORD}
    assert client.post("/api/auth/login", json=both, headers=ORIGIN).status_code == 422
    assert client.post("/api/auth/login", json={}, headers=ORIGIN).status_code == 422


# --- recovery -------------------------------------------------------------------------


def test_a_recovery_code_resets_the_password_once_and_signs_out_other_devices(client, open_signup):
    codes = _signup(client).json()["recovery_codes"]
    stolen_cookie = client.cookies.get("modeer_session")
    new_password = "a brand new passphrase"

    client.cookies.clear()
    response = client.post(
        "/api/auth/recover",
        json={"email": "alice@example.com", "code": codes[0].lower(), "new_password": new_password},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    assert response.json()["recovery_codes_left"] == 9
    assert client.get("/api/users/me").status_code == 200, "recovering signs this device in"

    assert _login(client, password=new_password).status_code == 200
    assert _login(client).status_code == 401, "the old password still works"

    client.cookies.clear()
    client.cookies.set("modeer_session", stolen_cookie, path="/api")
    assert client.get("/api/users/me").status_code == 401, "an old session survived recovery"

    client.cookies.clear()
    again = client.post(
        "/api/auth/recover",
        json={"email": "alice@example.com", "code": codes[0], "new_password": "yet another one"},
        headers=ORIGIN,
    )
    assert again.status_code == 401, "a recovery code worked twice"


def test_a_wrong_recovery_code_changes_nothing(client, open_signup):
    _signup(client)
    client.cookies.clear()
    response = client.post(
        "/api/auth/recover",
        json={
            "email": "alice@example.com",
            "code": "AAAA-BBBB-CCCC",
            "new_password": "whatever it is",
        },
        headers=ORIGIN,
    )
    assert response.status_code == 401
    assert _login(client).status_code == 200


def test_regenerating_codes_needs_the_password_and_retires_the_old_ones(client, open_signup):
    old = _signup(client).json()["recovery_codes"]
    refused = client.post(
        "/api/auth/recovery-codes", json={"password": "wrong password!"}, headers=ORIGIN
    )
    assert refused.status_code == 403, "a wrong confirmation must not look like a lost session"
    fresh = client.post("/api/auth/recovery-codes", json={"password": PASSWORD}, headers=ORIGIN)
    assert fresh.status_code == 200
    assert client.get("/api/auth/account").json()["recovery_codes_left"] == 10

    client.cookies.clear()
    stale = client.post(
        "/api/auth/recover",
        json={"email": "alice@example.com", "code": old[0], "new_password": "whatever it is"},
        headers=ORIGIN,
    )
    assert stale.status_code == 401


# --- changing the password ------------------------------------------------------------


def test_changing_the_password_needs_the_current_one_and_ends_other_sessions(client, open_signup):
    _signup(client)
    other_device = client.cookies.get("modeer_session")

    wrong = client.post(
        "/api/auth/password",
        json={"current_password": "not it at all", "new_password": "a new passphrase"},
        headers=ORIGIN,
    )
    assert wrong.status_code == 403, "a wrong confirmation must not look like a lost session"
    ok = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "a new passphrase"},
        headers=ORIGIN,
    )
    assert ok.status_code == 200
    assert client.get("/api/users/me").status_code == 200, "this device was signed out"

    client.cookies.clear()
    client.cookies.set("modeer_session", other_device, path="/api")
    assert client.get("/api/users/me").status_code == 401


def test_an_access_key_account_can_set_its_first_password(
    client, open_signup, make_user, monkeypatch
):
    legacy = make_user("Ken", email="ken@example.com")
    key = "k" * 40
    monkeypatch.setattr(
        settings, "auth_access_keys", {legacy.id: hashlib.sha256(key.encode()).hexdigest()}
    )
    client.post("/api/auth/login", json={"access_key": key}, headers=ORIGIN)
    assert client.get("/api/auth/account").json()["has_password"] is False

    first = client.post(
        "/api/auth/password", json={"new_password": "ken's own passphrase"}, headers=ORIGIN
    )
    assert first.status_code == 200
    assert len(first.json()["recovery_codes"]) == 10
    assert (
        _login(client, email="ken@example.com", password="ken's own passphrase").status_code == 200
    )


# --- account data and deletion --------------------------------------------------------


def test_no_secret_hash_ever_leaves_the_server(client, open_signup, db):
    _signup(client)
    account = db.scalar(select(User).where(User.email == "alice@example.com"))
    code_hashes = list(
        db.scalars(select(RecoveryCode.code_hash).where(RecoveryCode.user_id == account.id))
    )
    everything = client.get("/api/users/me").text + client.get("/api/users/me/export").text
    everything += client.get("/api/auth/account").text
    assert account.password_hash not in everything
    assert not any(h in everything for h in code_hashes)


def test_a_deleted_account_is_asked_to_sign_in_not_told_it_is_unknown(client, open_signup, db):
    _signup(client)
    account_id = client.get("/api/users/me").json()["id"]
    assert db.scalar(select(RecoveryCode).where(RecoveryCode.user_id == account_id))
    cookie = client.cookies.get("modeer_session")
    deleted = client.post("/api/users/me/delete", json={"confirm": "DELETE"}, headers=ORIGIN)
    assert deleted.status_code == 204, deleted.text
    leftover = db.scalar(select(RecoveryCode).where(RecoveryCode.user_id == account_id))
    assert leftover is None, "recovery codes outlived the account"

    client.cookies.set("modeer_session", cookie, path="/api")
    assert client.get("/api/users/me").status_code == 401


def test_the_sign_in_email_of_a_password_account_is_not_changed_by_a_session(client, open_signup):
    _signup(client)
    moved = client.patch("/api/users/me", json={"email": "attacker@example.com"}, headers=ORIGIN)
    assert moved.status_code == 400
    assert _login(client).status_code == 200


def test_profile_fields_are_bounded(client, open_signup):
    _signup(client)
    too_long = client.patch("/api/users/me", json={"profile": {"bio": "x" * 5000}}, headers=ORIGIN)
    too_many = client.patch(
        "/api/users/me", json={"profile": {f"k{i}": "v" for i in range(30)}}, headers=ORIGIN
    )
    assert (too_long.status_code, too_many.status_code) == (422, 422)


# --- memory consent --------------------------------------------------------------------


class _Counting(LLMProvider):
    name = "counting"

    def __init__(self):
        self.extraction_calls = 0

    async def stream_chat(self, *, system, messages, model, temperature, max_tokens):
        if "# ACTIVE AGENT:" in system:
            yield "A reply."
        else:
            self.extraction_calls += 1
            yield (
                '[{"scope":"shared","agent_id":null,"category":"context","key":"location",'
                '"value":"Cairo","confidence":0.95,"sensitive":false}]'
            )


def test_switching_off_automatic_memory_stops_learning_but_not_saving(
    client, open_signup, db, monkeypatch
):
    counting = _Counting()
    monkeypatch.setattr(provider_module, "_make_provider", lambda: counting)
    provider_module.get_llm_provider.cache_clear()
    monkeypatch.setattr(settings, "memory_extraction", "llm")
    try:
        _signup(client)
        assert client.get("/api/users/me").json()["memory_auto"] is True

        off = client.patch("/api/users/me", json={"memory_auto": False}, headers=ORIGIN)
        assert off.status_code == 200 and off.json()["memory_auto"] is False
        client.post(
            "/api/agents/modeer/chat/stream", json={"message": "I live in Cairo."}, headers=ORIGIN
        )
        assert counting.extraction_calls == 0, "a provider call was spent learning anyway"
        assert db.scalar(select(SharedMemory)) is None

        saved = client.post(
            "/api/memory/shared", json={"key": "location", "value": "Cairo"}, headers=ORIGIN
        )
        assert saved.status_code == 201, "switching off learning must not block saving by hand"

        client.patch("/api/users/me", json={"memory_auto": True}, headers=ORIGIN)
        client.post(
            "/api/agents/modeer/chat/stream", json={"message": "I study law too."}, headers=ORIGIN
        )
        assert counting.extraction_calls == 1, "positive control: learning resumes when switched on"
    finally:
        provider_module.get_llm_provider.cache_clear()


# --- operator last resort ---------------------------------------------------------------


def test_the_operator_can_let_in_someone_who_lost_password_and_codes(
    client, open_signup, monkeypatch, tmp_path
):
    import provision_user

    assert _signup(client, email="locked@example.com").status_code == 201
    stale = dict(client.cookies)

    output = tmp_path / "key.json"
    args = ["--rotate", "--clear-password", "--email", "Locked@Example.com "]
    assert provision_user.main([*args, "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf8"))
    monkeypatch.setattr(settings, "auth_access_keys", payload["AUTH_ACCESS_KEYS_entry"])

    client.cookies.clear()
    client.cookies.update(stale)
    assert client.get("/api/users/me").status_code == 401, "old sessions must end"
    assert _login(client, email="locked@example.com").status_code == 401, "old password"

    by_key = client.post(
        "/api/auth/login", json={"access_key": payload["access_key"]}, headers=ORIGIN
    )
    assert by_key.status_code == 200
    assert client.get("/api/auth/account").json() == {
        "has_password": False,
        "recovery_codes_left": 0,
        "email": "locked@example.com",
    }
    fresh = client.post(
        "/api/auth/password", json={"new_password": "a brand new passphrase"}, headers=ORIGIN
    )
    assert fresh.status_code == 200 and len(fresh.json()["recovery_codes"]) == 10
    assert (
        _login(client, email="locked@example.com", password="a brand new passphrase").status_code
        == 200
    )


def test_clear_password_needs_rotate(tmp_path):
    import provision_user

    with pytest.raises(SystemExit):
        provision_user.main(
            ["--clear-password", "--email", "a@example.com", "--output", str(tmp_path / "k.json")]
        )
