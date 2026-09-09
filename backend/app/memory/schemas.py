from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryBase(BaseModel):
    category: str = "general"
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1)
    source: str = "user"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    sensitive: bool = False


class SharedMemoryCreate(MemoryBase):
    pinned: bool = False


class SharedMemoryUpdate(BaseModel):
    category: str | None = None
    key: str | None = None
    value: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    sensitive: bool | None = None
    pinned: bool | None = None


class SharedMemoryRead(MemoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    scope: str
    pinned: bool
    created_at: datetime
    updated_at: datetime


class AgentMemoryCreate(MemoryBase):
    agent_id: str


class AgentMemoryUpdate(BaseModel):
    category: str | None = None
    key: str | None = None
    value: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    sensitive: bool | None = None


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
