from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: A stored fact is a sentence, not a document. Whatever is here is pasted into
#: every prompt that agent builds, so an unbounded value would push the rest of
#: the context out and spend the account's allowance on one turn.
MAX_VALUE = 2000
KEY = Field(min_length=1, max_length=120)


def _not_blank(value: str | None) -> str | None:
    if value is not None and not value.strip():
        raise ValueError("must not be blank")
    return value.strip() if isinstance(value, str) else value


class MemoryBase(BaseModel):
    category: str = "general"
    key: str = KEY
    # Read models inherit this, so no maximum here: a row saved before the cap
    # existed must still be readable. Writes are capped below.
    value: str = Field(min_length=1)
    source: str = "user"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    sensitive: bool = False


class SharedMemoryCreate(MemoryBase):
    value: str = Field(min_length=1, max_length=MAX_VALUE)
    pinned: bool = False

    _clean = field_validator("key", "value")(_not_blank)


class SharedMemoryUpdate(BaseModel):
    category: str | None = None
    key: str | None = Field(default=None, min_length=1, max_length=120)
    value: str | None = Field(default=None, min_length=1, max_length=MAX_VALUE)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    sensitive: bool | None = None
    pinned: bool | None = None

    _clean = field_validator("key", "value")(_not_blank)


class SharedMemoryRead(MemoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    scope: str
    pinned: bool
    created_at: datetime
    updated_at: datetime


class AgentMemoryCreate(MemoryBase):
    agent_id: str
    value: str = Field(min_length=1, max_length=MAX_VALUE)

    _clean = field_validator("key", "value")(_not_blank)


class AgentMemoryUpdate(BaseModel):
    category: str | None = None
    key: str | None = Field(default=None, min_length=1, max_length=120)
    value: str | None = Field(default=None, min_length=1, max_length=MAX_VALUE)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    sensitive: bool | None = None

    _clean = field_validator("key", "value")(_not_blank)


class AgentMemoryRead(MemoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    scope: str
    agent_id: str
    created_at: datetime
    updated_at: datetime


class MemoryCandidateRead(BaseModel):
    scope: str
    agent_id: str | None
    category: str
    key: str
    value: str
    confidence: float
    sensitive: bool
    stored: bool
    reason: str
