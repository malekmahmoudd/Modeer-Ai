from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, DbSession
from app.goals import service
from app.goals.schemas import GoalCreate, GoalRead, GoalUpdate

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalRead])
def list_goals(user: CurrentUser, db: DbSession, status: str | None = None):
    return service.list_goals(db, user.id, status)


@router.post("", response_model=GoalRead, status_code=201)
def create_goal(data: GoalCreate, user: CurrentUser, db: DbSession):
    return service.create_goal(db, user.id, data)


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(goal_id: str, data: GoalUpdate, user: CurrentUser, db: DbSession):
    goal = service.update_goal(db, user.id, goal_id, data)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: str, user: CurrentUser, db: DbSession):
    if not service.delete_goal(db, user.id, goal_id):
        raise HTTPException(status_code=404, detail="Goal not found")
