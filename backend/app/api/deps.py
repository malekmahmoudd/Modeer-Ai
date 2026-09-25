"""Shared FastAPI dependencies.

Invite-only mode resolves the signed session and ignores identity headers.
Development demo mode may select a user with X-User-Id for local isolation tests.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import authenticated_id, session_epoch_matches
from app.core.config import settings
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
            if settings.auth_required:
                # A signed session for an account that no longer exists: that is
                # a sign-in problem, and the client's 401 handling sends them to
                # the login page.
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Please sign in")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown user")
        # A cookie from a generation the account has since revoked is spent.
        if not session_epoch_matches(request, user):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in")
        refuse_if_suspended(user)
        return user
    return get_or_create_demo_user(db)


SUSPENDED = "This account is suspended. Contact whoever runs this service."


def refuse_if_suspended(user: User) -> None:
    """An operator stopped this account: nothing it asks for is served."""
    if getattr(user, "suspended_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SUSPENDED)


CurrentUser = Annotated[User, Depends(get_current_user)]
