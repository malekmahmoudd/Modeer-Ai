"""Signing in, signing up, and getting back in.

Two ways to sign in, side by side:

* email and password — accounts created through signup, or key accounts that
  have since set a password;
* an operator-issued access key — the invite-only model, which keeps working.

A lost password is recovered with one of the single-use recovery codes shown at
signup. No email is sent, so nothing here depends on a mail service.

Every endpoint that checks a secret is throttled per email (and signup per
client address), because an open form is an open invitation to guess.
"""

import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core import passwords
from app.core.auth import COOKIE, key_user, session_epoch_matches, sign_session
from app.core.config import settings
from app.core.usage import BudgetExceeded, charge
from app.db.base import utcnow
from app.db.models import RecoveryCode, User
from app.users.service import get_by_id

router = APIRouter(prefix="/auth", tags=["auth"])

#: Attempts allowed per email in a 15-minute window, across sign-in and
#: recovery — generous for a person mistyping, useless for guessing.
ATTEMPTS_PER_EMAIL = 10
#: Accounts one client address may create in an hour.
SIGNUPS_PER_ADDRESS = 5
WRONG_SIGN_IN = "That email and password don't match an account."
WRONG_RECOVERY = "That email and recovery code don't match an account."


# --- request bodies ---------------------------------------------------------------


def _normalise_email(value: str) -> str:
    return value.strip().lower()


def _check_password(value: str) -> str:
    problem = passwords.password_problem(value)
    if problem:
        raise ValueError(problem)
    return value


class Login(BaseModel):
    """Either an access key, or an email and password."""

    access_key: str | None = Field(default=None, min_length=32, max_length=256)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=1, max_length=passwords.MAX_PASSWORD)

    @model_validator(mode="after")
    def _one_way_in(self) -> "Login":
        by_key = self.access_key is not None
        by_password = self.email is not None and self.password is not None
        if by_key == by_password:
            raise ValueError("Sign in with an email and password, or with an access key")
        return self


class Signup(BaseModel):
    email: EmailStr
    password: str
    display_name: str = Field(min_length=1, max_length=60)

    _password = field_validator("password")(_check_password)

    @field_validator("display_name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Tell us what to call you")
        return value.strip()


class Recover(BaseModel):
    email: EmailStr
    code: str = Field(min_length=8, max_length=40)
    new_password: str

    _password = field_validator("new_password")(_check_password)


class ChangePassword(BaseModel):
    current_password: str | None = Field(default=None, max_length=passwords.MAX_PASSWORD)
    new_password: str

    _password = field_validator("new_password")(_check_password)


class ConfirmPassword(BaseModel):
    password: str = Field(min_length=1, max_length=passwords.MAX_PASSWORD)


# --- helpers ------------------------------------------------------------------------


def _same_origin(request: Request) -> None:
    if request.headers.get("origin", "").rstrip("/") != settings.frontend_url.rstrip("/"):
        raise HTTPException(403, "Request origin is not allowed")


def _throttle(kind: str, subject: str, limit: int, seconds: int) -> None:
    """Count an attempt; refuse once there have been too many.

    The subject is hashed before it is stored: the usage table should not become
    a list of the email addresses and IP addresses that tried to get in.
    """
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:40]
    try:
        charge(f"{kind}:{digest}", kind, 1, limit, seconds)
    except BudgetExceeded as exc:
        raise HTTPException(
            429,
            "Too many attempts. Please wait a few minutes and try again.",
            headers={"Retry-After": str(int(exc.retry_after or seconds))},
        ) from exc


def _client_address(request: Request) -> str:
    # Behind Caddy the first X-Forwarded-For entry is the real client: Caddy
    # replaces a forwarded header sent by the client rather than extending it.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _set_session(response: Response, account: User, *, epoch: int | None = None) -> None:
    response.set_cookie(
        COOKIE,
        sign_session(account.id, (account.session_epoch or 0) if epoch is None else epoch),
        max_age=settings.session_seconds,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path="/api",
    )
    response.headers["Cache-Control"] = "no-store"


def _issue_codes(db, account: User) -> list[str]:
    """Replace every recovery code with a fresh set. Returns them in the clear —
    the only time they ever exist in the clear."""
    for existing in list(account.recovery_codes):
        db.delete(existing)
    codes = passwords.new_recovery_codes()
    for code in codes:
        db.add(RecoveryCode(user_id=account.id, code_hash=passwords.hash_recovery_code(code)))
    return codes


def _codes_left(account: User) -> int:
    return sum(1 for code in account.recovery_codes if code.used_at is None)


def _by_email(db, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == _normalise_email(email)))


def _lock_credentials(db, account: User, request: Request | None = None) -> None:
    """Serialize credential mutations in the database, including on SQLite.

    A no-op UPDATE takes the account's write lock until commit/rollback. Refresh
    after acquiring it: a concurrent recovery may have changed the credentials
    while this request was waiting. All credential mutations use this lock.
    """
    result = db.execute(
        update(User).where(User.id == account.id).values(session_epoch=User.session_epoch),
        execution_options={"synchronize_session": False},
    )
    if result.rowcount != 1:
        raise HTTPException(401, "Please sign in")
    db.refresh(account)
    db.expire(account, ["recovery_codes"])
    if request is not None and not session_epoch_matches(request, account):
        raise HTTPException(401, "Please sign in")


# --- routes -------------------------------------------------------------------------


@router.get("/status")
def status():
    return {"required": settings.auth_required, "signup_enabled": settings.signup_enabled}


@router.post("/login")
def login(body: Login, request: Request, response: Response, db: DbSession):
    if not settings.auth_required:
        raise HTTPException(400, "Sign-in is disabled for local development")
    _same_origin(request)

    if body.access_key is not None:
        user_id = key_user(body.access_key)
        account = get_by_id(db, user_id) if user_id else None
        if not user_id or account is None:
            raise HTTPException(401, "Invalid access key")
    else:
        _throttle("login", _normalise_email(body.email), ATTEMPTS_PER_EMAIL, 900)
        account = _by_email(db, body.email)
        # Checked even when there is no such account, so the answer takes the
        # same time and says the same thing either way.
        if not passwords.verify_password(body.password, account.password_hash if account else None):
            raise HTTPException(401, WRONG_SIGN_IN)

    _set_session(response, account)
    return {"signed_in": True}


@router.post("/signup", status_code=201)
def signup(body: Signup, request: Request, response: Response, db: DbSession):
    if not settings.signup_enabled or not settings.auth_required:
        raise HTTPException(404, "Signup is not available")
    _same_origin(request)
    _throttle("signup", _client_address(request), SIGNUPS_PER_ADDRESS, 3600)

    email = _normalise_email(body.email)
    if _by_email(db, email) is not None:
        raise HTTPException(
            409, "An account with that email already exists. Sign in, or use a recovery code."
        )
    account = User(
        email=email,
        display_name=body.display_name,
        password_hash=passwords.hash_password(body.password),
    )
    db.add(account)
    try:
        db.flush()
    except IntegrityError as exc:  # two signups for one address at once
        db.rollback()
        raise HTTPException(409, "An account with that email already exists.") from exc
    codes = _issue_codes(db, account)
    db.commit()

    _set_session(response, account)
    return {"signed_in": True, "recovery_codes": codes}


@router.post("/recover")
def recover(body: Recover, request: Request, response: Response, db: DbSession):
    if not settings.auth_required:
        raise HTTPException(400, "Sign-in is disabled for local development")
    _same_origin(request)
    email = _normalise_email(body.email)
    _throttle("login", email, ATTEMPTS_PER_EMAIL, 900)

    account = _by_email(db, email)
    if account is not None:
        _lock_credentials(db, account)
    wanted = passwords.hash_recovery_code(body.code)
    match = None
    for code in account.recovery_codes if account else []:
        # Every unused code is compared, in constant time, even after a match.
        if code.used_at is None and hmac.compare_digest(code.code_hash, wanted):
            match = match or code
    if account is None or match is None:
        raise HTTPException(401, WRONG_RECOVERY)

    claimed = db.execute(
        update(RecoveryCode)
        .where(RecoveryCode.id == match.id, RecoveryCode.used_at.is_(None))
        .values(used_at=utcnow())
    )
    if claimed.rowcount != 1:
        raise HTTPException(401, WRONG_RECOVERY)
    account.password_hash = passwords.hash_password(body.new_password)
    # A lost password may be a stolen one: end every other session.
    account.session_epoch = (account.session_epoch or 0) + 1
    issued_epoch = account.session_epoch
    db.commit()

    _set_session(response, account, epoch=issued_epoch)
    return {"signed_in": True, "recovery_codes_left": _codes_left(account)}


@router.get("/account")
def account_security(user: CurrentUser):
    """What the Account page needs to show about signing in."""
    return {
        "has_password": user.password_hash is not None,
        "recovery_codes_left": _codes_left(user),
        "email": user.email,
    }


@router.post("/password")
def change_password(
    body: ChangePassword, request: Request, response: Response, user: CurrentUser, db: DbSession
):
    """Change the password — or set a first one on an access-key account.

    Setting a first password also issues recovery codes, since the account can
    now be locked out by forgetting it.
    """
    # Throttling uses a separate transaction, so it must precede the write lock.
    _throttle("login", _normalise_email(user.email or user.id), ATTEMPTS_PER_EMAIL, 900)
    _lock_credentials(db, user, request)
    first_password = user.password_hash is None
    if not first_password:
        if not passwords.verify_password(body.current_password or "", user.password_hash):
            # 403, not 401: the session is fine, only this confirmation failed —
            # and a 401 would send the person to the login page mid-form.
            raise HTTPException(403, "Your current password is not right.")
    elif not user.email:
        raise HTTPException(400, "Add an email address to this account before setting a password.")

    user.password_hash = passwords.hash_password(body.new_password)
    user.session_epoch = (user.session_epoch or 0) + 1  # other devices sign in again
    issued_epoch = user.session_epoch
    codes = _issue_codes(db, user) if first_password else None
    db.commit()

    _set_session(response, user, epoch=issued_epoch)  # this device stays signed in
    return {"changed": True, "recovery_codes": codes}


@router.post("/recovery-codes")
def regenerate_recovery_codes(
    body: ConfirmPassword, request: Request, user: CurrentUser, db: DbSession
):
    """A fresh set of codes; every earlier code stops working."""
    _throttle("login", _normalise_email(user.email or user.id), ATTEMPTS_PER_EMAIL, 900)
    _lock_credentials(db, user, request)
    if user.password_hash is None:
        raise HTTPException(400, "Set a password first; recovery codes recover a password.")
    if not passwords.verify_password(body.password, user.password_hash):
        raise HTTPException(403, "That password is not right.")  # see change_password
    codes = _issue_codes(db, user)
    db.commit()
    return {"recovery_codes": codes}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/api")
    return {"signed_in": False}


@router.post("/sign-out-everywhere")
def sign_out_everywhere(user: CurrentUser, db: DbSession, response: Response, request: Request):
    """End every session for this account, on every device.

    Bumps the account's session generation, which the signature covers, so
    cookies already issued stop verifying. Rotating the shared signing secret
    would do the same thing to everyone at once; this affects one account.

    Use it when a device is lost. If the access KEY itself has leaked, this is
    not enough — the key still works. Rotate it with
    ``python provision_user.py --rotate``.
    """
    _lock_credentials(db, user, request)
    user.session_epoch = (user.session_epoch or 0) + 1
    db.commit()
    response.delete_cookie(COOKIE, path="/api")
    return {"signed_in": False, "sessions_revoked": True}
