from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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
    created_at: datetime
