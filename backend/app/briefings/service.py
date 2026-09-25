"""Daily briefing.

Lightweight and honest: it only reflects information the product already holds
(goals + shared personal context). It never claims to know calendar events,
emails, weather or anything external.
"""
from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import today_for
from app.db.models import Briefing, User
from app.goals import service as goal_service
from app.memory import service as memory_service
from app.tracking import service as tracking

# Route a goal/priority to the specialist most likely to help with it.
_AGENT_HINTS: list[tuple[str, str, str]] = [
    ("study", "📚",
     r"exam|study|studying|learn|revision|revise|course|gpa|semester|thesis|dissertation"),
    ("career", "💼",
     r"cv|resume|interview|job|internship|career|promotion|linkedin|job offer|recruiter"),
    ("fitness", "🏋️",
     r"workout|gym|train|training|run|running|fitness|exercise|weight|marathon"),
    ("finance", "💰",
     r"save|saving|savings|budget|debt|invest|money|finance|financial|rent"),
    ("travel", "✈️", r"trip|travel|flight|holiday|vacation|itinerary|visa"),
    ("writing", "✍️", r"write|writing|essay|draft|article|blog|book|newsletter|paper"),
    ("research", "🔎", r"research|investigate|analy[sz]e|compare sources|literature"),
    ("email", "✉️", r"email|reply|inbox|message to|reach out"),
    ("shopping", "🛍️", r"buy|purchase|laptop|phone|headphones|choose between"),
]
_AGENT_HINT_RES = [
    (slug, icon, re.compile(rf"\b(?:{pat})\b", re.I)) for slug, icon, pat in _AGENT_HINTS
]


def _agent_for(text: str) -> tuple[str | None, str]:
    for slug, icon, pattern in _AGENT_HINT_RES:
        if pattern.search(text):
            return slug, icon
    return None, "•"


def _today(user: User) -> str:
    """The user's own date: a briefing is for their day, not the server's."""
    return today_for(user).isoformat()


def _countdown(target, today: date) -> str:
    """Text like "Due Thu 1 Oct — in 6 days", for a goal with a target date."""
    if target is None:
        return ""
    day = target.date() if hasattr(target, "date") else target
    days = (day - today).days
    label = f"{day:%a} {day.day} {day:%b}"
    if days < 0:
        return f"Was due {label}"
    if days == 0:
        return f"Due today ({label})"
    return f"Due {label} — in {days} day{'s' if days != 1 else ''}"


def build_items(db: Session, user: User) -> tuple[str, list[dict]]:
    today = today_for(user)
    goals = goal_service.list_goals(db, user.id, status="active")
    shared = memory_service.list_shared(db, user.id)
    items: list[dict] = []

    top_goal = None
    for i, g in enumerate(sorted(goals, key=lambda g: g.priority)[:3]):
        slug, icon = _agent_for(f"{g.title} {g.detail}")
        if i == 0:
            top_goal = g.title
        items.append(
            {
                "icon": icon,
                "text": g.title,
                "detail": " · ".join(
                    part for part in (_countdown(g.target_date, today), g.detail or "") if part
                ),
                "source": "goal",
                "agent": slug,
            }
        )

    if not goals:
        for m in [s for s in shared if s.category in ("goals", "career", "education")][:2]:
            slug, icon = _agent_for(m.value)
            items.append(
                {
                    "icon": icon,
                    "text": f"{m.key.replace('_', ' ').capitalize()}: {m.value}",
                    "detail": "",
                    "source": "memory",
                    "agent": slug,
                }
            )

    # Dated things first: they are why today is different from yesterday.
    items[:0] = tracking.briefing_items(db, user.id, today=today)
    if today.weekday() == 0:  # Monday, in the user's own week
        review = tracking.weekly_review(db, user.id, today=today)
        items.append(
            {
                "icon": "🗓️",
                "text": "Your week",
                "detail": review["summary"],
                "source": "review",
                "agent": "modeer",
            }
        )

    items.append(
        {
            "icon": "🧭",
            "text": "Plan today's priorities with me",
            "detail": "",
            "source": "prompt",
            "agent": "modeer",
        }
    )

    name = user.display_name if user.display_name and user.display_name != "You" else None
    if len(items) == 1:
        summary = (
            "I don't have your goals or context yet. Tell me what you're working on "
            "and this becomes genuinely useful."
        )
    elif top_goal:
        summary = f"Your priorities point at “{top_goal}” first."
    else:
        summary = "Here's what looks worth your attention, based on what the team knows."
    if name and len(items) > 1:
        summary = f"{name}, {summary[0].lower()}{summary[1:]}"
    return summary, items


def get_today(db: Session, user: User) -> Briefing | None:
    return db.scalar(
        select(Briefing)
        .where(
            Briefing.user_id == user.id,
            Briefing.generated_for_date == _today(user),
        )
        .order_by(Briefing.created_at.desc())
    )


def get_or_generate_today(db: Session, user: User, *, force: bool = False) -> Briefing:
    existing = get_today(db, user)
    if existing and not force:
        return existing
    summary, items = build_items(db, user)
    briefing = Briefing(
        user_id=user.id,
        summary=summary,
        items=items,
        generated_for_date=_today(user),
    )
    db.add(briefing)
    db.flush()
    return briefing
