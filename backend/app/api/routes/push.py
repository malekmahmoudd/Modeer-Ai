"""Reminders on the lock screen (Web Push): the key the browser needs, and
turning them on or off for this browser."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.push import service, webpush

router = APIRouter(prefix="/push", tags=["push"])


class Keys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=64)


class Subscription(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)
    keys: Keys


class Endpoint(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000)


@router.get("/key")
def public_key(user: CurrentUser, db: DbSession) -> dict:
    """The applicationServerKey for pushManager.subscribe()."""
    if not settings.push_enabled:
        raise HTTPException(404, "Reminders are not available")
    return {"public_key": webpush.public_key(service.signing_key(db))}


@router.post("/subscribe", status_code=201)
def subscribe(body: Subscription, request: Request, user: CurrentUser, db: DbSession) -> dict:
    if not settings.push_enabled:
        raise HTTPException(404, "Reminders are not available")
    try:
        service.subscribe(
            db,
            user,
            body.endpoint,
            body.keys.p256dh,
            body.keys.auth,
            request.headers.get("user-agent"),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"subscribed": True}


@router.post("/unsubscribe")
def unsubscribe(body: Endpoint, user: CurrentUser, db: DbSession) -> dict:
    return {"unsubscribed": service.unsubscribe(db, user, body.endpoint)}


@router.post("/test")
async def test(user: CurrentUser, db: DbSession) -> dict:
    """A reminder right now, to see what it looks like."""
    ar = (user.locale or "en") == "ar"
    delivered = await service.send(
        db,
        user,
        {
            "title": "فريق AI" if ar else "Fareeq AI",
            "body": "التذكيرات تعمل على هذا الجهاز." if ar else "Reminders work on this device.",
            "url": "/account",
        },
    )
    db.commit()  # keep the removal of any browser that has gone away
    if not delivered:
        raise HTTPException(409, "No browser accepted the reminder")
    return {"delivered": delivered}
