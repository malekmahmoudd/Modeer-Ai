"""Saved prompts with {blanks}: the person's own, for one teammate or any."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.agents.registry import get_agent
from app.api.deps import CurrentUser, DbSession
from app.db.models import PromptTemplate

router = APIRouter(prefix="/templates", tags=["templates"])

#: Enough for a personal library; each one is only text.
MAX_TEMPLATES = 100


class TemplateIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=4000)
    agent_id: str | None = None

    @field_validator("title", "body")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("agent_id")
    @classmethod
    def _agent(cls, value: str | None) -> str | None:
        if value is not None and get_agent(value) is None:
            raise ValueError("Unknown agent")
        return value


def _read(row: PromptTemplate) -> dict:
    return {"id": row.id, "title": row.title, "body": row.body, "agent_id": row.agent_id}


def _own(db, user, template_id: str) -> PromptTemplate:
    row = db.get(PromptTemplate, template_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Template not found")
    return row


@router.get("")
def list_templates(user: CurrentUser, db: DbSession, agent_id: str | None = None):
    stmt = select(PromptTemplate).where(PromptTemplate.user_id == user.id)
    if agent_id:
        stmt = stmt.where(
            (PromptTemplate.agent_id == agent_id) | (PromptTemplate.agent_id.is_(None))
        )
    return [_read(r) for r in db.scalars(stmt.order_by(PromptTemplate.title))]


@router.post("", status_code=201)
def create_template(data: TemplateIn, user: CurrentUser, db: DbSession):
    count = len(
        list(db.scalars(select(PromptTemplate.id).where(PromptTemplate.user_id == user.id)))
    )
    if count >= MAX_TEMPLATES:
        raise HTTPException(409, "You have the most templates allowed. Delete one first.")
    row = PromptTemplate(user_id=user.id, **data.model_dump())
    db.add(row)
    db.flush()
    return _read(row)


@router.put("/{template_id}")
def update_template(template_id: str, data: TemplateIn, user: CurrentUser, db: DbSession):
    row = _own(db, user, template_id)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.flush()
    return _read(row)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, user: CurrentUser, db: DbSession):
    db.delete(_own(db, user, template_id))
