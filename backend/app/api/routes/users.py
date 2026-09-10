from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.core.auth import COOKIE
from app.users.schemas import ProfileUpdate, UserRead
from app.users.service import delete_user, export_user_data, update_profile

router = APIRouter(prefix="/users", tags=["users"])


class DeleteAccount(BaseModel):
    """Deleting an account is irreversible, so it takes a deliberate confirmation."""

    confirm: str = Field(description="Must be the exact word DELETE")


@router.get("/me", response_model=UserRead)
def get_me(user: CurrentUser) -> UserRead:
    return user


@router.patch("/me", response_model=UserRead)
def patch_me(data: ProfileUpdate, user: CurrentUser, db: DbSession) -> UserRead:
    return update_profile(db, user, data)


@router.get("/me/export")
def export_me(user: CurrentUser, db: DbSession) -> JSONResponse:
    """Download everything stored about this account as one JSON file.

    Sent as an attachment rather than a rendered body: this is the user's data
    to keep, and it contains the full text of every conversation.
    """
    payload = export_user_data(db, user)
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": 'attachment; filename="modeer-export.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/me/delete", status_code=204)
def delete_me(data: DeleteAccount, user: CurrentUser, db: DbSession, response: Response):
    """Erase this account and everything belonging to it. There is no undo.

    A POST rather than DELETE so the confirmation travels in a body that every
    client sends reliably, and so it cannot be triggered by a bare link.
    """
    if data.confirm != "DELETE":
        # 422 rather than 400: the body is the thing that is wrong.
        raise HTTPException(status_code=422, detail="Send confirm: DELETE to erase the account")
    delete_user(db, user)
    db.commit()
    response.delete_cookie(COOKIE, path="/api")
