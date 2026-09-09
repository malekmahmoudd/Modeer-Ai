from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    onboarded: bool | None = None
    profile: dict | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str | None
    display_name: str
    onboarded: bool
    profile: dict
    created_at: datetime
