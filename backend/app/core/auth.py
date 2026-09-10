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


def sign_session(user_id: str) -> str:
    payload = f"{user_id}.{int(time.time()) + settings.session_seconds}"
    signature = hmac.new(
        settings.auth_secret.encode(),
        (payload + settings.auth_access_keys[user_id]).encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def session_user(token: str) -> str | None:
    try:
        user_id, expiry, signature = token.split(".")
        digest = settings.auth_access_keys[user_id]
        expected = hmac.new(
            settings.auth_secret.encode(), f"{user_id}.{expiry}{digest}".encode(), hashlib.sha256
        ).hexdigest()
        if int(expiry) > time.time() and hmac.compare_digest(signature, expected):
            return user_id
    except (ValueError, KeyError):
        pass
    return None


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
