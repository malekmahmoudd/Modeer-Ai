from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import reject_null


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(default="", max_length=2000)
    priority: int = Field(default=3, ge=1, le=5)
    target_date: datetime | None = None


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    detail: str | None = Field(default=None, max_length=2000)
    priority: int | None = Field(default=None, ge=1, le=5)
    status: str | None = Field(default=None, pattern="^(active|done|paused)$")
    target_date: datetime | None = None

    _required_values = field_validator("title", "detail", "priority", "status", mode="before")(
        reject_null
    )


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    detail: str
    priority: int
    status: str
    target_date: datetime | None
    created_at: datetime
    updated_at: datetime
