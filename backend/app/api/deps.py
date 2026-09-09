"""Shared FastAPI dependencies.

Auth is intentionally minimal for the MVP: a single local user. Pass an
``X-User-Id`` header to act as a specific user (used by tests to prove
isolation); otherwise the stable demo user is used.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.users.service import get_by_id, get_or_create_demo_user

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    x_user_id: Annotated[str | None, Header()] = None,
) -> User:
    if x_user_id:
        user = get_by_id(db, x_user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown user"
            )
        return user
    return get_or_create_demo_user(db)


CurrentUser = Annotated[User, Depends(get_current_user)]
