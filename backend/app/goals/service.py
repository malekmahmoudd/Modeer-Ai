from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Goal
from app.goals.schemas import GoalCreate, GoalUpdate


def list_goals(
    db: Session, user_id: str, status: str | None = None
) -> list[Goal]:
    stmt = select(Goal).where(Goal.user_id == user_id)
    if status:
        stmt = stmt.where(Goal.status == status)
    stmt = stmt.order_by(Goal.priority, Goal.created_at.desc())
    return list(db.scalars(stmt))


def create_goal(db: Session, user_id: str, data: GoalCreate) -> Goal:
    goal = Goal(user_id=user_id, **data.model_dump())
    db.add(goal)
    db.flush()
    return goal


def update_goal(
    db: Session, user_id: str, goal_id: str, data: GoalUpdate
) -> Goal | None:
    goal = db.scalar(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
    )
    if goal is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.flush()
    return goal


def delete_goal(db: Session, user_id: str, goal_id: str) -> bool:
    goal = db.scalar(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
    )
    if goal is None:
        return False
    db.delete(goal)
    db.flush()
    return True
