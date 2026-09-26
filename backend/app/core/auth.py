"""Invite-only authentication: hashed access keys and expiring signed cookies."""

import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from app.core.config import settings

COOKIE = "modeer_session"


def key_user(key: str) -> str | None:
    digest = hashlib.sha256(key.encode()).hexdigest()
    for user_id, expected in settings.auth_access_keys.items():
        if hmac.compare_digest(digest, expected):
            return user_id
    return None


def _key_binding(user_id: str) -> str:
    """What else a session signature is bound to, beyond the account id.

    For an account that signs in with an operator-issued access key, the key's
    digest: removing or rotating the key in AUTH_ACCESS_KEYS then invalidates
    every session minted with it. A password account has no key; its sessions
    are revoked through the session epoch, which changes with the password.
    """
    return settings.auth_access_keys.get(user_id, "")


def sign_session(user_id: str, epoch: int = 0, session_id: str = "") -> str:
    """Mint a session cookie for one account.

    ``epoch`` is the account's session generation. It travels inside the signed
    payload so a person can invalidate their own sessions everywhere by bumping
    it, without rotating the shared signing secret — which would sign everyone
    out. ``session_id`` names the signed-in device (app.core.sessions), so one
    device can be signed out on its own.
    """
    expiry = int(time.time()) + settings.session_seconds
    payload = (
        f"{user_id}.{epoch}.{session_id}.{expiry}" if session_id else f"{user_id}.{epoch}.{expiry}"
    )
    signature = hmac.new(
        settings.auth_secret.encode(),
        (payload + _key_binding(user_id)).encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def session_claims(token: str) -> tuple[str, int, str | None] | None:
    """Verify the cookie and return (user_id, epoch, device id or None), or None.

    Does not touch the database: the epoch and the device are checked where the
    account is loaded (app.core.sessions.session_ok) — which is also what turns
    away a deleted account. Cookies minted before devices were tracked have no
    device id and stay valid until they expire.
    """
    try:
        parts = token.split(".")
        if len(parts) == 5:
            user_id, epoch, session_id, expiry, signature = parts
            payload = f"{user_id}.{epoch}.{session_id}.{expiry}"
        else:
            user_id, epoch, expiry, signature = parts
            session_id, payload = None, f"{user_id}.{epoch}.{expiry}"
        digest = _key_binding(user_id)
        expected = hmac.new(
            settings.auth_secret.encode(),
            f"{payload}{digest}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if int(expiry) > time.time() and hmac.compare_digest(signature, expected):
            return user_id, int(epoch), session_id or None
    except (ValueError, KeyError):
        pass
    return None


def session_user(token: str) -> str | None:
    claims = session_claims(token)
    return claims[0] if claims else None


def session_epoch_matches(request: Request, user) -> bool:
    """Whether the caller's cookie belongs to the account's current generation.

    Checked where the account row is already loaded, so revocation costs no
    extra query. Always true when authentication is off, since there is no
    cookie to revoke.
    """
    if not settings.auth_required:
        return True
    claims = session_claims(request.cookies.get(COOKIE, ""))
    return bool(claims) and claims[1] == (getattr(user, "session_epoch", 0) or 0)


def caller_id(request: Request) -> str | None:
    """Dependency form of :func:`authenticated_id`.

    Declared with ``Depends`` it is resolved before the request body is parsed,
    so an anonymous caller is turned away with 401 instead of being told what the
    body should have looked like.
    """
    return authenticated_id(request)


def authenticated_id(request: Request) -> str | None:
    if not settings.auth_required:
        return request.headers.get("x-user-id")
    # Cookie-based mutations must originate from the configured frontend.
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(
        "origin", ""
    ).rstrip("/") != settings.frontend_url.rstrip("/"):
        raise HTTPException(403, "Request origin is not allowed")
    user_id = session_user(request.cookies.get(COOKIE, ""))
    if not user_id:
        raise HTTPException(401, "Please sign in")
    return user_id
