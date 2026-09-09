from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.users.schemas import ProfileUpdate

DEMO_EMAIL = "demo@modeer.local"


def get_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def get_or_create_demo_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(email=DEMO_EMAIL, display_name="You", onboarded=False)
        db.add(user)
        db.flush()
    return user


def update_profile(db: Session, user: User, data: ProfileUpdate) -> User:
    payload = data.model_dump(exclude_unset=True)
    if "profile" in payload and payload["profile"] is not None:
        merged = dict(user.profile or {})
        merged.update(payload.pop("profile"))
        user.profile = merged
    for field, value in payload.items():
        setattr(user, field, value)
    db.flush()
    return user
