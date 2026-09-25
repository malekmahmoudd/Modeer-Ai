"""Follow-ups, saved plans, check-ins, the weekly review and the allowance.

Everything here is also reachable from chat ("save this plan", "done with day
3", mentioning a date or something you did); these routes are for screens and
for putting things right by hand.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agents.registry import get_agent
from app.api.deps import CurrentUser, DbSession
from app.core.auth import caller_id
from app.core.clock import today_for
from app.core.usage import allowance
from app.db.models import CheckIn, Conversation, Goal, Message, Plan
from app.tracking import plans as plan_service
from app.tracking import service

router = APIRouter(tags=["tracking"])


# --- schemas ------------------------------------------------------------------------


class FollowUpCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    due_on: date
    ends_on: date | None = None
    agent_id: str = "modeer"


class FollowUpUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    due_on: date | None = None
    ends_on: date | None = None
    status: str | None = Field(default=None, pattern="^(pending|done|dismissed)$")


class PlanFromMessage(BaseModel):
    message_id: str


class PlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, pattern="^(active|done|archived)$")
    goal_id: str | None = None
    #: A new start day: every "Day N" / weekday step is dated again from it. A
    #: December trip saved in September starts in December.
    starts_on: date | None = None


class StepUpdate(BaseModel):
    done: bool


def _followup(row) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "title": row.title,
        "due_on": row.due_on.isoformat(),
        "ends_on": row.ends_on.isoformat() if row.ends_on else None,
        "status": row.status,
        "asked_at": row.asked_at.isoformat() if row.asked_at else None,
        "source_message_id": row.source_message_id,
    }


def _plan(row: Plan) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "goal_id": row.goal_id,
        "title": row.title,
        "status": row.status,
        "starts_on": row.starts_on.isoformat(),
        "source_message_id": row.source_message_id,
        "done": sum(1 for s in row.steps if s.done_at),
        "steps": [
            {
                "id": s.id,
                "position": s.position,
                "text": s.text,
                "due_on": s.due_on.isoformat() if s.due_on else None,
                "done": s.done_at is not None,
            }
            for s in row.steps
        ],
    }


def _checkin(row) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "text": row.text,
        "amount": row.amount,
        "unit": row.unit,
        "details": row.details,
        "logged_on": row.logged_on.isoformat(),
    }


def _known_agent(slug: str) -> None:
    if get_agent(slug) is None:
        raise HTTPException(status_code=404, detail="Unknown agent")


def _calendar(body: str, filename: str) -> Response:
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# --- follow-ups -----------------------------------------------------------------------


@router.get("/followups")
def list_followups(user: CurrentUser, db: DbSession, status: str | None = None):
    return [_followup(f) for f in service.list_followups(db, user.id, status=status)]


@router.post("/followups", status_code=201)
def create_followup(data: FollowUpCreate, user: CurrentUser, db: DbSession):
    _known_agent(data.agent_id)
    if data.ends_on and data.ends_on < data.due_on:
        raise HTTPException(status_code=422, detail="The end date is before the start date.")
    row, _ = service.add_followup(
        db,
        user.id,
        agent_id=data.agent_id,
        title=data.title.strip(),
        due_on=data.due_on,
        ends_on=data.ends_on,
    )
    return _followup(row)


@router.patch("/followups/{followup_id}")
def update_followup(followup_id: str, data: FollowUpUpdate, user: CurrentUser, db: DbSession):
    row = service.get_followup(db, user.id, followup_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    changes = data.model_dump(exclude_unset=True)
    if "due_on" in changes and changes["due_on"] != row.due_on:
        row.asked_at = None  # a new date is a new thing to ask about
    for field, value in changes.items():
        if value is not None:
            setattr(row, field, value)
    db.flush()
    return _followup(row)


@router.delete("/followups/{followup_id}", status_code=204)
def delete_followup(followup_id: str, user: CurrentUser, db: DbSession):
    row = service.get_followup(db, user.id, followup_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    db.delete(row)


@router.get("/followups/calendar.ics")
def followups_calendar(user: CurrentUser, db: DbSession):
    """Every pending follow-up as an all-day event, to add to any calendar."""
    events = [
        (f.id, f.due_on, f.title) for f in service.list_followups(db, user.id, status="pending")
    ]
    return _calendar(service.to_ics(events, name="Fareeq follow-ups"), "fareeq-followups.ics")


# --- plans ------------------------------------------------------------------------------


@router.get("/plans")
def list_plans(user: CurrentUser, db: DbSession, status: str | None = None):
    return [_plan(p) for p in plan_service.list_plans(db, user.id, status=status)]


@router.post("/plans", status_code=201)
def save_plan(data: PlanFromMessage, user: CurrentUser, db: DbSession):
    """Keep an agent's reply as a checklist — what "save this plan" does in chat."""
    found = db.execute(
        select(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Message.id == data.message_id, Conversation.user_id == user.id)
    ).first()
    if found is None or found[0].role != "assistant":
        raise HTTPException(status_code=404, detail="Reply not found")
    message, conversation = found
    agent = get_agent(conversation.agent_id)
    today = today_for(user)
    plan = plan_service.save_from_reply(
        db,
        user.id,
        conversation.agent_id,
        message,
        today=today,
        fallback_title=f"Plan with {agent.name if agent else 'your team'} — {today:%d %b}",
    )
    if plan is None:
        raise HTTPException(status_code=422, detail="That reply has no steps to keep as a plan.")
    return _plan(plan)


def _own_plan(db, user_id: str, plan_id: str) -> Plan:
    plan = plan_service.get_plan(db, user_id, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, user: CurrentUser, db: DbSession):
    return _plan(_own_plan(db, user.id, plan_id))


@router.patch("/plans/{plan_id}")
def update_plan(plan_id: str, data: PlanUpdate, user: CurrentUser, db: DbSession):
    plan = _own_plan(db, user.id, plan_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("goal_id"):
        goal = db.get(Goal, changes["goal_id"])
        if goal is None or goal.user_id != user.id:
            raise HTTPException(status_code=404, detail="Goal not found")
    starts_on = changes.pop("starts_on", None)
    for field, value in changes.items():
        if value is not None or field == "goal_id":
            setattr(plan, field, value)
    if starts_on is not None:
        plan_service.reschedule(plan, starts_on)
    db.flush()
    return _plan(plan)


@router.patch("/plans/{plan_id}/steps/{step_id}")
def update_step(plan_id: str, step_id: str, data: StepUpdate, user: CurrentUser, db: DbSession):
    plan = _own_plan(db, user.id, plan_id)
    if plan_service.set_step(db, plan, step_id, data.done) is None:
        raise HTTPException(status_code=404, detail="Step not found")
    return _plan(plan)


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: str, user: CurrentUser, db: DbSession):
    db.delete(_own_plan(db, user.id, plan_id))


@router.get("/plans/{plan_id}/calendar.ics")
def plan_calendar(plan_id: str, user: CurrentUser, db: DbSession):
    plan = _own_plan(db, user.id, plan_id)
    events = [(s.id, s.due_on, s.text) for s in plan.steps if s.due_on and not s.done_at]
    if not events:
        raise HTTPException(status_code=422, detail="This plan has no dated steps.")
    return _calendar(service.to_ics(events, name=plan.title), "fareeq-plan.ics")


# --- check-ins ---------------------------------------------------------------------------


@router.get("/checkins")
def list_checkins(
    user: CurrentUser, db: DbSession, agent_id: str | None = None, since: date | None = None
):
    return [_checkin(c) for c in service.list_checkins(db, user.id, agent_id=agent_id, since=since)]


@router.delete("/checkins/{checkin_id}", status_code=204)
def delete_checkin(checkin_id: str, user: CurrentUser, db: DbSession):
    row = db.get(CheckIn, checkin_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Check-in not found")
    db.delete(row)


# --- the week, and the allowance --------------------------------------------------------


@router.get("/briefings/week")
def week(user: CurrentUser, db: DbSession):
    """The last seven days and the next seven, from what is tracked. No model call."""
    return service.weekly_review(db, user.id, today=today_for(user))


@router.get("/usage/me")
def my_allowance(user: CurrentUser, account: Annotated[str | None, Depends(caller_id)]):
    """How much of today's AI allowance is left, in tokens and in rough messages."""
    return allowance(account or "local-demo")
