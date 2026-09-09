from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BriefingItem(BaseModel):
    icon: str
    text: str
    source: str  # "goal" | "memory" | "prompt"


class BriefingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    summary: str
    items: list[dict]
    generated_for_date: str
    created_at: datetime
