from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import DbSession
from app.core.auth import COOKIE, key_user, sign_session
from app.core.config import settings
from app.users.service import get_by_id

router = APIRouter(prefix="/auth", tags=["auth"])


class Login(BaseModel):
    access_key: str = Field(min_length=32, max_length=256)


@router.get("/status")
def status():
    return {"required": settings.auth_required}


@router.post("/login")
def login(body: Login, request: Request, response: Response, db: DbSession):
    if not settings.auth_required:
        raise HTTPException(400, "Sign-in is disabled for local development")
    if request.headers.get("origin", "").rstrip("/") != settings.frontend_url.rstrip("/"):
        raise HTTPException(403, "Request origin is not allowed")
    user_id = key_user(body.access_key)
    if not user_id or not get_by_id(db, user_id):
        raise HTTPException(401, "Invalid access key")
    response.set_cookie(
        COOKIE,
        sign_session(user_id),
        max_age=settings.session_seconds,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path="/api",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"signed_in": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/api")
    return {"signed_in": False}
