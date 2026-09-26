"""Signing in, signing up, and getting back in.

Two ways to sign in, side by side:

* email and password — accounts created through signup, or key accounts that
  have since set a password;
* an operator-issued access key — the invite-only model, which keeps working.

A lost password is recovered with one of the single-use recovery codes shown at
signup. No email is sent, so nothing here depends on a mail service.

Two-step sign-in is optional: an authenticator-app code (app.core.totp) after
the password or key. A recovery code works in its place when the phone is lost.
Each sign-in is a device (app.core.sessions) that can be signed out on its own.

Every endpoint that checks a secret is throttled per email (and signup per
client address), because an open form is an open invitation to guess.
"""

import hashlib
import hmac
import re
from datetime import UTC

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, refuse_if_suspended
from app.core import passwords, totp
from app.core import sessions as devices
from app.core.auth import COOKIE, key_user, session_claims, sign_session
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
    #: The second step, when the account has one: a 6-digit authenticator code
    #: or a recovery code.
    code: str | None = Field(default=None, max_length=40)

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


class TwoFactorCode(BaseModel):
    code: str = Field(min_length=6, max_length=40)


class TwoFactorOff(BaseModel):
    password: str = Field(min_length=1, max_length=passwords.MAX_PASSWORD)
    code: str = Field(min_length=6, max_length=40)


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


def _set_session(
    response: Response,
    account: User,
    db,
    request: Request,
    method: str,
    *,
    epoch: int | None = None,
) -> None:
    """Sign this device in: a device row, and a cookie that names it."""
    session_id = devices.start(db, account, request, method)
    db.commit()
    response.set_cookie(
        COOKIE,
        sign_session(
            account.id, (account.session_epoch or 0) if epoch is None else epoch, session_id
        ),
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
    if request is not None and not devices.session_ok(db, request, account):
        raise HTTPException(401, "Please sign in")


def _use_recovery_code(db, account: User, code: str) -> bool:
    """Spend one unused recovery code, comparing every code in constant time."""
    wanted = passwords.hash_recovery_code(code)
    match = None
    for row in account.recovery_codes:
        if row.used_at is None and hmac.compare_digest(row.code_hash, wanted):
            match = match or row
    if match is None:
        return False
    claimed = db.execute(
        update(RecoveryCode)
        .where(RecoveryCode.id == match.id, RecoveryCode.used_at.is_(None))
        .values(used_at=utcnow())
    )
    return claimed.rowcount == 1


def _second_step(db, account: User, code: str) -> bool:
    """An authenticator code (not already used), or else a recovery code."""
    if account.totp_secret:
        step = totp.verify(account.totp_secret, code, last_step=account.totp_last_step)
        if step is not None:
            account.totp_last_step = step
            return True
    return len(code.strip()) >= 8 and _use_recovery_code(db, account, code.strip())


_BROWSERS = [
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
]
_SYSTEMS = [
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("CrOS", "ChromeOS"),
    ("Mac OS X", "Mac"),
    ("Windows", "Windows"),
    ("Linux", "Linux"),
]


def _utc(moment):
    """An ISO time that says it is UTC, which SQLite's naive values do not."""
    if moment is None:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).isoformat()


def _describe(user_agent: str | None) -> dict:
    """ "Chrome on Mac": enough to recognise a device in the list."""
    ua = user_agent or ""
    browser = next((name for mark, name in _BROWSERS if mark in ua), None)
    system = next((name for mark, name in _SYSTEMS if re.search(re.escape(mark), ua)), None)
    return {"browser": browser, "system": system}


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

    refuse_if_suspended(account)
    if account.totp_enabled_at is not None:
        if not body.code:
            # The first step was right; ask for the second. No cookie yet.
            return {"signed_in": False, "two_factor_required": True}
        _throttle("second-step", account.id, ATTEMPTS_PER_EMAIL, 900)
        if not _second_step(db, account, body.code):
            raise HTTPException(401, "That code isn't right. Check your authenticator app.")
    _set_session(response, account, db, request, "key" if body.access_key else "password")
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

    _set_session(response, account, db, request, "signup")
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

    _set_session(response, account, db, request, "recovery", epoch=issued_epoch)
    return {"signed_in": True, "recovery_codes_left": _codes_left(account)}


@router.get("/account")
def account_security(user: CurrentUser):
    """What the Account page needs to show about signing in."""
    return {
        "has_password": user.password_hash is not None,
        "recovery_codes_left": _codes_left(user),
        "email": user.email,
        "two_factor": user.totp_enabled_at is not None,
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

    # This device stays signed in, as a fresh device row; the others have ended.
    _set_session(response, user, db, request, "refresh", epoch=issued_epoch)
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
def logout(request: Request, response: Response, db: DbSession):
    """Sign this device out. Its device row ends too, so the cookie is dead even
    if a copy of it survives somewhere."""
    claims = session_claims(request.cookies.get(COOKIE, ""))
    if claims and claims[2]:
        account = get_by_id(db, claims[0])
        if account is not None:
            devices.revoke(db, account, claims[2])
    response.delete_cookie(COOKIE, path="/api")
    return {"signed_in": False}


# --- devices ------------------------------------------------------------------------


@router.get("/sessions")
def list_sessions(request: Request, user: CurrentUser, db: DbSession):
    """Where this account is signed in. Sessions from before devices were
    tracked are not listed; "sign out every device" still ends them."""
    current = devices.current_id(request)
    return [
        {
            "id": row.id,
            "current": row.id == current,
            **_describe(row.user_agent),
            "network": row.ip_prefix,
            "method": row.method,
            "signed_in_at": _utc(row.created_at),
            "last_seen_at": _utc(row.last_seen_at),
        }
        for row in devices.active(db, user)
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def end_session(
    session_id: str, request: Request, response: Response, user: CurrentUser, db: DbSession
):
    """Sign one device out. Its next request is refused and goes to sign-in."""
    if not devices.revoke(db, user, session_id):
        raise HTTPException(404, "That device is not signed in")
    if session_id == devices.current_id(request):
        response.delete_cookie(COOKIE, path="/api")


# --- two-step sign-in -----------------------------------------------------------------


@router.post("/2fa/setup")
def two_factor_setup(body: ConfirmPassword, request: Request, user: CurrentUser, db: DbSession):
    """Start setting up an authenticator: a new secret, shown once, confirmed by
    the first code it makes. A password is needed first, because its recovery
    codes are what gets you in if the phone is lost."""
    _throttle("login", _normalise_email(user.email or user.id), ATTEMPTS_PER_EMAIL, 900)
    _lock_credentials(db, user, request)
    if user.password_hash is None:
        raise HTTPException(
            400,
            "Set a password first: its recovery codes are your way back in "
            "if you lose your phone.",
        )
    if not passwords.verify_password(body.password, user.password_hash):
        raise HTTPException(403, "That password is not right.")
    if user.totp_enabled_at is not None:
        raise HTTPException(409, "Two-step sign-in is already on.")
    user.totp_pending = totp.new_secret()
    db.commit()
    return {
        "secret": user.totp_pending,
        "uri": totp.provisioning_uri(user.totp_pending, user.email or user.display_name),
    }


@router.post("/2fa/enable")
def two_factor_enable(body: TwoFactorCode, request: Request, user: CurrentUser, db: DbSession):
    _throttle("second-step", user.id, ATTEMPTS_PER_EMAIL, 900)
    _lock_credentials(db, user, request)
    if not user.totp_pending:
        raise HTTPException(400, "Start the setup again.")
    step = totp.verify(user.totp_pending, body.code)
    if step is None:
        raise HTTPException(
            403, "That code isn't right. Check the time on your phone, and try the newest code."
        )
    user.totp_secret, user.totp_pending = user.totp_pending, None
    user.totp_last_step = step
    user.totp_enabled_at = utcnow().replace(tzinfo=None)
    db.commit()
    return {"two_factor": True, "recovery_codes_left": _codes_left(user)}


@router.post("/2fa/disable")
def two_factor_disable(body: TwoFactorOff, request: Request, user: CurrentUser, db: DbSession):
    """Turn it off: the password and a current code (or a recovery code)."""
    _throttle("second-step", user.id, ATTEMPTS_PER_EMAIL, 900)
    _lock_credentials(db, user, request)
    if user.totp_enabled_at is None:
        return {"two_factor": False}
    if not passwords.verify_password(body.password, user.password_hash):
        raise HTTPException(403, "That password is not right.")
    if not _second_step(db, user, body.code):
        raise HTTPException(403, "That code isn't right.")
    user.totp_secret = user.totp_pending = None
    user.totp_enabled_at = user.totp_last_step = None
    db.commit()
    return {"two_factor": False}


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
    devices.revoke_all(db, user)
    db.commit()
    response.delete_cookie(COOKIE, path="/api")
    return {"signed_in": False, "sessions_revoked": True}
