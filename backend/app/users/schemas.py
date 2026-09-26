from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.clock import valid_zone
from app.core.validation import reject_null

#: The profile is pasted into every prompt ("About the user"), so it is bounded
#: like stored memories are.
MAX_PROFILE_KEYS = 20
MAX_PROFILE_VALUE = 300


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    email: EmailStr | None = None
    onboarded: bool | None = None
    profile: dict | None = None
    #: Whether Modeer may learn facts from this person's messages automatically.
    memory_auto: bool | None = None
    #: IANA timezone, e.g. "Europe/London". Null clears it (agents use UTC).
    timezone: str | None = Field(default=None, max_length=64)
    #: Interface language. Null follows the browser.
    locale: str | None = Field(default=None, pattern="^(en|ar)$")

    _required_values = field_validator(
        "display_name", "onboarded", "profile", "memory_auto", mode="before"
    )(reject_null)

    @field_validator("timezone")
    @classmethod
    def _real_zone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if valid_zone(value) is None:
            raise ValueError("Unknown timezone; use an IANA name such as Europe/London")
        return value.strip()

    @field_validator("profile")
    @classmethod
    def _bounded(cls, value: dict | None) -> dict | None:
        if value is None:
            return value
        if len(value) > MAX_PROFILE_KEYS:
            raise ValueError(f"At most {MAX_PROFILE_KEYS} profile fields")
        for key, item in value.items():
            if not isinstance(key, str) or not 0 < len(key) <= 40:
                raise ValueError("Profile field names must be 1-40 characters")
            if item is not None and len(str(item)) > MAX_PROFILE_VALUE:
                raise ValueError(f"Profile values must be at most {MAX_PROFILE_VALUE} characters")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str | None
    display_name: str
    onboarded: bool
    profile: dict
    memory_auto: bool
    timezone: str | None = None
    locale: str | None = None
    created_at: datetime
