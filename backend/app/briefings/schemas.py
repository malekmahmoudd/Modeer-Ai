from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BriefingItem(BaseModel):
    icon: str
    text: str
    detail: str = ""
    source: str  # "goal" | "memory" | "prompt"
    agent: str | None = None  # specialist slug this relates to, if any


class BriefingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    summary: str
    items: list[dict]
    generated_for_date: str
    created_at: datetime
