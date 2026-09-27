"""The CV builder: versions of one person's CV, each aimed at a role."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.cv.docx import render
from app.cv.schemas import CvCopy, CvData, CvIn
from app.db.models import CvDocument

router = APIRouter(prefix="/cv", tags=["cv"])

#: One per role someone is applying for is plenty.
MAX_CVS = 20

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _read(row: CvDocument) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "target_role": row.target_role,
        "data": CvData.model_validate(row.data or {}).model_dump(),
        "updated_at": row.updated_at,
    }


def _own(db, user, cv_id: str) -> CvDocument:
    row = db.get(CvDocument, cv_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "CV not found")
    return row


def _room(db, user) -> None:
    count = len(list(db.scalars(select(CvDocument.id).where(CvDocument.user_id == user.id))))
    if count >= MAX_CVS:
        raise HTTPException(409, "You have the most CVs allowed. Delete one first.")


@router.get("")
def list_cvs(user: CurrentUser, db: DbSession):
    rows = db.scalars(
        select(CvDocument)
        .where(CvDocument.user_id == user.id)
        .order_by(CvDocument.updated_at.desc())
    )
    return [_read(r) for r in rows]


@router.post("", status_code=201)
def create_cv(data: CvIn, user: CurrentUser, db: DbSession):
    _room(db, user)
    row = CvDocument(
        user_id=user.id,
        title=data.title,
        target_role=data.target_role,
        data=data.data.model_dump(),
    )
    db.add(row)
    db.flush()
    return _read(row)


@router.get("/{cv_id}")
def get_cv(cv_id: str, user: CurrentUser, db: DbSession):
    return _read(_own(db, user, cv_id))


@router.put("/{cv_id}")
def update_cv(cv_id: str, data: CvIn, user: CurrentUser, db: DbSession):
    row = _own(db, user, cv_id)
    row.title = data.title
    row.target_role = data.target_role
    row.data = data.data.model_dump()
    db.flush()
    return _read(row)


@router.post("/{cv_id}/copy", status_code=201)
def copy_cv(cv_id: str, data: CvCopy, user: CurrentUser, db: DbSession):
    """A new version for another role, starting from this one."""
    source = _own(db, user, cv_id)
    _room(db, user)
    row = CvDocument(
        user_id=user.id,
        title=data.title.strip() or source.title,
        target_role=data.target_role,
        data=dict(source.data or {}),
    )
    db.add(row)
    db.flush()
    return _read(row)


@router.delete("/{cv_id}", status_code=204)
def delete_cv(cv_id: str, user: CurrentUser, db: DbSession):
    db.delete(_own(db, user, cv_id))


@router.get("/{cv_id}/docx")
def export_docx(cv_id: str, user: CurrentUser, db: DbSession):
    row = _own(db, user, cv_id)
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", row.title).strip("-") or "cv"
    return Response(
        render(CvData.model_validate(row.data or {})),
        media_type=DOCX,
        headers={"Content-Disposition": f'attachment; filename="{name}.docx"'},
    )
