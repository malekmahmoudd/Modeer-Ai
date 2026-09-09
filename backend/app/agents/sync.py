"""Mirror the code-defined agent registry into the ``agents`` table."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.registry import all_agents
from app.db.models import Agent


def sync_agents(db: Session) -> int:
    count = 0
    for cfg in all_agents():
        row = db.get(Agent, cfg.id)
        fields = {
            "name": cfg.name,
            "role": cfg.role,
            "description": cfg.description,
            "accent": cfg.accent,
            "icon": cfg.icon,
            "is_assistant": cfg.is_assistant,
            "sort_order": cfg.sort_order,
            "config_version": cfg.prompt_version,
        }
        if row is None:
            db.add(Agent(id=cfg.id, **fields))
        else:
            for k, v in fields.items():
                setattr(row, k, v)
        count += 1
    db.flush()
    return count
