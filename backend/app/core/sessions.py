"""Signed-in devices: one row per sign-in, checked on every request.

The signed cookie says who you are; this row says the device has not been
signed out since. A cookie minted before devices were tracked has no id and is
checked by the account's session generation alone until it expires.
"""

from __future__ import annotations

import ipaddress
from datetime import timedelta

from fastapi import Request
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.auth import COOKIE, session_claims
from app.core.config import settings
from app.db.base import utcnow
from app.db.models import User, UserSession

#: last_seen_at is written at most this often, not on every request.
SEEN_EVERY = timedelta(minutes=5)
#: Ended sessions are deleted this long after they end.
KEEP_ENDED = timedelta(days=30)


def _now():
    return utcnow().replace(tzinfo=None)


def _client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def network_prefix(address: str) -> str | None:
    """ "203.0.113.x" or "2001:db8:1::/48": enough to recognise a place, not a
    person's exact address."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    if ip.version == 4:
        return ".".join(str(ip).split(".")[:3]) + ".x"
    return str(ipaddress.ip_network(f"{ip}/48", strict=False))


def start(db: Session, user: User, request: Request, method: str) -> str:
    """Record a new signed-in device and return its id for the cookie."""
    row = UserSession(
        user_id=user.id,
        epoch=user.session_epoch or 0,
        method=method,
        user_agent=(request.headers.get("user-agent") or "")[:200] or None,
        ip_prefix=network_prefix(_client_address(request)),
        last_seen_at=_now(),
        expires_at=_now() + timedelta(seconds=settings.session_seconds),
    )
    db.add(row)
    db.flush()
    return row.id


def current_id(request: Request) -> str | None:
    claims = session_claims(request.cookies.get(COOKIE, ""))
    return claims[2] if claims else None


def session_ok(db: Session, request: Request, user: User) -> bool:
    """Whether the caller's cookie is still good for this account: the right
    generation, and (when it names a device) that device not signed out."""
    if not settings.auth_required:
        return True
    claims = session_claims(request.cookies.get(COOKIE, ""))
    if not claims or claims[0] != user.id or claims[1] != (user.session_epoch or 0):
        return False
    sid = claims[2]
    if sid is None:
        return True
    row = db.get(UserSession, sid)
    if row is None or row.user_id != user.id or row.revoked_at is not None:
        return False
    now = _now()
    if row.last_seen_at is None or now - row.last_seen_at > SEEN_EVERY:
        row.last_seen_at = now
    return True


def active(db: Session, user: User) -> list[UserSession]:
    """The devices signed in now, most recently used first."""
    now = _now()
    return list(
        db.scalars(
            select(UserSession)
            .where(
                UserSession.user_id == user.id,
                UserSession.revoked_at.is_(None),
                UserSession.epoch == (user.session_epoch or 0),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.last_seen_at.desc())
        )
    )


def revoke(db: Session, user: User, session_id: str) -> bool:
    row = db.get(UserSession, session_id)
    if row is None or row.user_id != user.id or row.revoked_at is not None:
        return False
    row.revoked_at = _now()
    db.flush()
    return True


def revoke_all(db: Session, user: User) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def sweep(db: Session) -> int:
    """Delete sessions that ended (signed out or expired) over 30 days ago."""
    cutoff = _now() - KEEP_ENDED
    result = db.execute(
        delete(UserSession).where(
            (UserSession.revoked_at < cutoff) | (UserSession.expires_at < cutoff)
        )
    )
    return result.rowcount or 0
