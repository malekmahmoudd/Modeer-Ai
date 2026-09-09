from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.users.schemas import ProfileUpdate, UserRead
from app.users.service import update_profile

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def get_me(user: CurrentUser) -> UserRead:
    return user


@router.patch("/me", response_model=UserRead)
def patch_me(data: ProfileUpdate, user: CurrentUser, db: DbSession) -> UserRead:
    return update_profile(db, user, data)
