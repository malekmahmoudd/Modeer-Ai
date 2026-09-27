"""Reminders on the lock screen: one short digest a day, at the hour the person
chose, in their own timezone and language.

It lists what is dated today and tomorrow (interviews, exams, trips starting)
and the plan steps due today. With details hidden, the lock screen shows only
how many things there are. Nothing is sent unless they turned it on in a
browser, and a browser that has gone away is forgotten.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import lang
from app.core.clock import now_for, zone
from app.core.config import settings
from app.db.base import utcnow
from app.db.models import FollowUp, PushSent, PushSubscription, ServerKey, User
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


def subscribe(db: Session, user: User, endpoint: str, p256dh: str, auth: str, agent: str | None):
    if not webpush.allowed_endpoint(endpoint):
        raise ValueError("That push service isn't supported.")
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if row is None:
        row = PushSubscription(endpoint=endpoint)
        db.add(row)
    row.user_id, row.p256dh, row.auth = user.id, p256dh, auth
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
        step = next((s for s in plan.steps if s.done_at is None), None)
        if step is not None and step.due_on == today:
            lines.append(f"{plan.title}: {step.text[:80]}")
    count = len(lines)
    if ar:
        title = "يومك مع فريق AI"
        hidden = "عندك شيء واحد اليوم." if count == 1 else f"عندك {lang.num(count)} أشياء اليوم."
    else:
        title = "Today with Fareeq AI"
        hidden = "You have 1 thing today." if count == 1 else f"You have {count} things today."
    details = _prefs(user).get("push_details", True)
    return title, ("\n".join(lines[:4]) if details else hidden), count


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
