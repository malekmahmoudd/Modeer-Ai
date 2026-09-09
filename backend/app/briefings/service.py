"""Daily briefing.

Lightweight and honest: it only reflects information the product already holds
(goals + shared personal context). It never claims to know calendar events,
emails, weather or anything external.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Briefing, User
from app.goals import service as goal_service
from app.memory import service as memory_service

_CATEGORY_ICON = {
    "education": "📚",
    "career": "💼",
    "goals": "🎯",
    "fitness": "🏋️",
    "context": "📌",
    "finance": "💰",
    "general": "•",
}


def _today() -> str:
    return date.today().isoformat()


def build_items(db: Session, user: User) -> tuple[str, list[dict]]:
    goals = goal_service.list_goals(db, user.id, status="active")
    shared = memory_service.list_shared(db, user.id)
    items: list[dict] = []

    for g in sorted(goals, key=lambda g: g.priority)[:3]:
        icon = "🎯" if g.priority > 1 else "⭐"
        items.append({"icon": icon, "text": g.title, "source": "goal"})

    if not goals:
        for m in [s for s in shared if s.category in ("goals", "career", "education")][:2]:
            items.append(
                {
                    "icon": _CATEGORY_ICON.get(m.category, "•"),
                    "text": f"{m.key.replace('_', ' ').capitalize()}: {m.value}",
                    "source": "memory",
                }
            )

    items.append(
        {
            "icon": "🗒️",
            "text": "Want help planning today's priorities?",
            "source": "prompt",
        }
    )

    name = user.display_name or "there"
    if len(items) == 1:
        summary = (
            f"Good day, {name}. I don't have goals or personal context saved yet — "
            f"tell Modeer what you're working on and this briefing gets useful."
        )
    else:
        summary = (
            f"Good day, {name}. Based on what you've told the team, here's what "
            f"seems worth your attention."
        )
    return summary, items


def get_today(db: Session, user: User) -> Briefing | None:
    return db.scalar(
        select(Briefing)
        .where(
            Briefing.user_id == user.id,
            Briefing.generated_for_date == _today(),
        )
        .order_by(Briefing.created_at.desc())
    )


def get_or_generate_today(
    db: Session, user: User, *, force: bool = False
) -> Briefing:
    existing = get_today(db, user)
    if existing and not force:
        return existing
    summary, items = build_items(db, user)
    briefing = Briefing(
        user_id=user.id,
        summary=summary,
        items=items,
        generated_for_date=_today(),
    )
    db.add(briefing)
    db.flush()
    return briefing
