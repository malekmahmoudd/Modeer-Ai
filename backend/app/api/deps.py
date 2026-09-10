"""Shared FastAPI dependencies.

Invite-only mode resolves the signed session and ignores identity headers.
Development demo mode may select a user with X-User-Id for local isolation tests.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import authenticated_id
from app.db.models import User
from app.db.session import get_db
from app.users.service import get_by_id, get_or_create_demo_user

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    request: Request,
) -> User:
    x_user_id = authenticated_id(request)
    if x_user_id:
        user = get_by_id(db, x_user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown user")
        return user
    return get_or_create_demo_user(db)


CurrentUser = Annotated[User, Depends(get_current_user)]
