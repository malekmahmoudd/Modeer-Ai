from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.clock import valid_zone
from app.core.validation import reject_null

#: The profile is pasted into every prompt ("About the user"), so it is bounded
#: like stored memories are.
MAX_PROFILE_KEYS = 20
MAX_PROFILE_VALUE = 300


class UIPreferences(BaseModel):
    """Interface state only; never included in model context."""

    front_desk: list[str] = Field(
        default_factory=lambda: ["study", "career", "research", "writing"], max_length=9
    )
    reading_size: int = Field(default=16, ge=14, le=24)
    reading_spacing: float = Field(default=1.85, ge=1.4, le=2.4)
    reading_width: int = Field(default=720, ge=480, le=960)

    @field_validator("front_desk")
    @classmethod
    def _specialists(cls, ids: list[str]) -> list[str]:
        from app.agents.registry import get_agent

        if len(ids) != len(set(ids)) or any(not get_agent(i) or i == "modeer" for i in ids):
            raise ValueError("Choose distinct specialists")
        return ids


class ProfileUpdate(BaseModel):
    ui_preferences: UIPreferences | None = None
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
        "display_name", "onboarded", "profile", "memory_auto", "ui_preferences", mode="before"
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
    ui_preferences: dict = Field(default_factory=dict)
    memory_auto: bool
    timezone: str | None = None
    locale: str | None = None
    created_at: datetime
