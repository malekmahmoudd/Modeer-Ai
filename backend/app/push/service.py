"""Reminders on the lock screen: one short digest a day, at the hour the person
chose, in their own timezone and language.

It lists what is dated today and tomorrow (interviews, exams, trips starting)
and the plan steps due today. With details hidden, the lock screen shows only
how many things there are. Nothing is sent unless they turned it on in a
browser, and a browser that has gone away is forgotten.

A subscription belongs to the signed-in device (UserSession) that made it.
Signing that device out, removing it from Account, signing out everywhere or a
password change ends its reminders: they are deleted there, and checked again
before every send. A sign-in that merely expired pauses them; the same account
signing in again on that browser carries them over (see ``claim_for_device``).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import lang
from app.core.clock import now_for, zone
from app.core.config import settings
from app.db.base import utcnow
from app.db.models import FollowUp, PushSent, PushSubscription, ServerKey, User, UserSession
from app.push import webpush
from app.tracking import plans as plan_service

logger = logging.getLogger(__name__)

DEFAULT_HOUR = 8
#: No reminder after this hour: turning it on at night waits for the morning.
LATEST_HOUR = 21


def signing_key(db: Session) -> str:
    """The VAPID key: configured, else made once and kept in the database."""
    if settings.vapid_private_key:
        return settings.vapid_private_key
    row = db.get(ServerKey, "vapid_private")
    if row is None:
        row = ServerKey(name="vapid_private", value=webpush.new_private_key())
        db.add(row)
        db.flush()
    return row.value


def _subject() -> str:
    url = settings.frontend_url
    return url if url.startswith("https://") else "mailto:push@fareeq.invalid"


def _now() -> datetime:
    return utcnow().replace(tzinfo=None)


def device_state(db: Session, user: User, sub: PushSubscription) -> str:
    """ "live", "expired" (the sign-in ran out; same account may carry it over)
    or "ended" (signed out, removed, another account, or a newer password)."""
    if not settings.auth_required:
        return "live"  # no sign-in at all: nothing to be signed out of
    if sub.session_id is None or sub.user_id != user.id:
        return "ended"
    row = db.get(UserSession, sub.session_id)
    if row is None or row.user_id != user.id or row.revoked_at is not None:
        return "ended"
    if row.epoch != (user.session_epoch or 0):
        return "ended"
    return "live" if row.expires_at > _now() else "expired"


def subscribe(
    db: Session,
    user: User,
    endpoint: str,
    p256dh: str,
    auth: str,
    agent: str | None,
    session_id: str | None,
):
    if not webpush.allowed_endpoint(endpoint):
        raise ValueError("That push service isn't supported.")
    if settings.auth_required and session_id is None:
        raise PermissionError("Sign in again to turn on reminders.")
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if row is None:
        row = PushSubscription(endpoint=endpoint)
        db.add(row)
    # The same browser may have belonged to someone else before: it is now this
    # account's, on this sign-in.
    row.user_id, row.p256dh, row.auth = user.id, p256dh, auth
    row.session_id = session_id
    row.user_agent = (agent or "")[:200] or None
    db.flush()
    return row


def unsubscribe(db: Session, user: User, endpoint: str) -> bool:
    row = db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id
        )
    )
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


def claim_for_device(db: Session, user: User, endpoint: str, session_id: str | None) -> bool:
    """Whether this browser gets this account's reminders on this sign-in.

    Carries a subscription over from a sign-in that simply expired, but only
    for the same account: one that was signed out, removed or belongs to
    someone else stays off until turned on again."""
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if row is None or row.user_id != user.id:
        return False
    if not settings.auth_required:
        return True
    if row.session_id == session_id:
        return device_state(db, user, row) == "live"
    if session_id is not None and device_state(db, user, row) == "expired":
        row.session_id = session_id
        db.flush()
        return True
    return False


def end_for_session(db: Session, session_id: str) -> None:
    """A device was signed out: its reminders stop now."""
    db.execute(delete(PushSubscription).where(PushSubscription.session_id == session_id))


def end_for_user(db: Session, user_id: str, *, keep_session: str | None = None) -> None:
    """Every device was signed out (or a password changed): reminders stop on
    all of them, except the device doing it when ``keep_session`` names it."""
    stmt = delete(PushSubscription).where(PushSubscription.user_id == user_id)
    if keep_session is not None:
        stmt = stmt.where(
            (PushSubscription.session_id.is_(None)) | (PushSubscription.session_id != keep_session)
        )
    db.execute(stmt)


def move_session(db: Session, old: str, new: str) -> None:
    """The device signed in again (a password change): keep its reminders."""
    for row in db.scalars(select(PushSubscription).where(PushSubscription.session_id == old)):
        row.session_id = new
    db.flush()


def _prefs(user: User) -> dict:
    return user.ui_preferences or {}


def digest(db: Session, user: User, today: date) -> tuple[str, str, int]:
    """(title, body, how many things) for today's reminder."""
    ar = (user.locale or "en") == "ar"
    tomorrow = today + timedelta(days=1)
    lines: list[str] = []
    for f in db.scalars(
        select(FollowUp).where(
            FollowUp.user_id == user.id,
            FollowUp.status == "pending",
            FollowUp.due_on.in_([today, tomorrow]),
        )
    ):
        if ar:
            lines.append(f"{'اليوم' if f.due_on == today else 'غدًا'}: {f.title}")
        else:
            lines.append(f"{'Today' if f.due_on == today else 'Tomorrow'}: {f.title}")
    for plan in plan_service.list_plans(db, user.id, status="active"):
        for step in plan.steps:
            if step.done_at is None and step.due_on == today:
                lines.append(f"{plan.title}: {step.text[:80]}")
    count = len(lines)
    if ar:
        title = "يومك مع فريق AI"
        hidden = "عندك شيء واحد اليوم." if count == 1 else f"عندك {lang.num(count)} أشياء اليوم."
    else:
        title = "Today with Fareeq AI"
        hidden = "You have 1 thing today." if count == 1 else f"You have {count} things today."
    details = _prefs(user).get("push_details", True)
    shown = lines[:4]
    if count > len(shown):  # a lock screen fits a few lines; say how many more
        more = count - len(shown)
        shown.append(f"و{lang.num(more)} أخرى" if ar else f"+{more} more")
    return title, ("\n".join(shown) if details else hidden), count


async def send(db: Session, user: User, message: dict) -> int:
    """Send to every browser this person turned reminders on in. Returns how
    many accepted it; ones that say they are gone are removed."""
    key = signing_key(db)
    body = json.dumps(message, ensure_ascii=False).encode()
    delivered = 0
    subs = list(db.scalars(select(PushSubscription).where(PushSubscription.user_id == user.id)))
    async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
        for sub in subs:
            if not webpush.allowed_endpoint(sub.endpoint):
                continue
            state = device_state(db, user, sub)
            if state == "ended":
                db.delete(sub)  # that device was signed out; never send again
                continue
            if state == "expired":
                continue  # paused until the same account signs in there again
            try:
                payload = webpush.encrypt(
                    body, webpush.unb64url(sub.p256dh), webpush.unb64url(sub.auth)
                )
                response = await client.post(
                    sub.endpoint,
                    content=payload,
                    headers={
                        "Authorization": webpush.vapid_header(sub.endpoint, key, _subject()),
                        "Content-Encoding": "aes128gcm",
                        "Content-Type": "application/octet-stream",
                        "TTL": "43200",
                        "Urgency": "normal",
                    },
                )
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("Push failed: %s", type(exc).__name__)
                continue
            if response.status_code in (404, 410):
                db.delete(sub)  # the browser unsubscribed or was reset
            elif response.status_code < 300:
                sub.last_sent_at = utcnow().replace(tzinfo=None)
                delivered += 1
            else:
                logger.warning("Push refused: status=%s", response.status_code)
    db.flush()
    return delivered


def _claim(db: Session, user: User, day: date) -> bool:
    """Mark today's digest as handled; False when it already was."""
    try:
        with db.begin_nested():
            db.add(PushSent(user_id=user.id, kind="digest", day=day))
        return True
    except IntegrityError:
        return False


async def send_due(db: Session, *, now: datetime | None = None) -> int:
    """Send today's digest to everyone whose hour has come. Returns how many."""
    users = list(
        db.scalars(select(User).where(User.id.in_(select(PushSubscription.user_id).distinct())))
    )
    sent = 0
    for user in users:
        if user.suspended_at is not None:
            continue
        local = now_for(user)[0] if now is None else now.astimezone(zone(user.timezone) or UTC)
        hour = int(_prefs(user).get("push_hour", DEFAULT_HOUR))
        if not hour <= local.hour < LATEST_HOUR:
            continue
        if not _claim(db, user, local.date()):
            continue
        title, body, count = digest(db, user, local.date())
        if count:
            sent += int(await send(db, user, {"title": title, "body": body, "url": "/plans"}) > 0)
        db.commit()
    return sent
