"""Documents: give a file to an agent, see its state, share or remove it.

Uploads are read in after the response (status "processing" → "ready" or
"failed"); poll GET /documents/{id}. Only the extracted text is kept.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel, Field

from app.agents.registry import get_agent
from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.usage import limited_caller
from app.db.models import Document
from app.documents import service

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentUpdate(BaseModel):
    shared: bool | None = None
    filename: str | None = Field(default=None, min_length=1, max_length=200)


def _read(doc: Document, *, preview: bool = False) -> dict:
    body = {
        "id": doc.id,
        "agent_id": doc.agent_id,
        "shared": doc.shared,
        "filename": doc.filename,
        "kind": doc.kind,
        "size_bytes": doc.size_bytes,
        "status": doc.status,
        "error": doc.error,
        "pages": doc.pages,
        "chars": doc.chars,
        "searchable_by_meaning": doc.embed_model is not None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }
    if preview:
        body["preview"] = doc.chunks[0].text[:600] if doc.chunks else ""
        body["chunks"] = len(doc.chunks)
    return body


@router.post("", status_code=202)
async def upload(
    # Charged first, before the account session opens a write of its own.
    _caller: Annotated[str | None, Depends(limited_caller)],
    request: Request,
    background: BackgroundTasks,
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    agent_id: Annotated[str, Form()],
    shared: Annotated[bool, Form()] = False,
):
    """Give a file to one agent (``shared`` gives it to the whole team)."""
    declared = int(request.headers.get("content-length") or 0)
    if declared > settings.document_max_bytes + 64 * 1024:
        raise HTTPException(413, "That file is over the size limit.")
    if get_agent(agent_id) is None:
        raise HTTPException(404, "Unknown agent")
    data = await file.read(settings.document_max_bytes + 1)
    try:
        doc = service.create(
            db,
            user.id,
            agent_id=agent_id,
            filename=file.filename or "document",
            data=data,
            shared=shared,
        )
    except service.Rejected as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    db.commit()  # the background read opens its own session and must see the row
    background.add_task(service.ingest, doc.id, data)
    return _read(doc)


@router.get("")
def list_documents(user: CurrentUser, db: DbSession):
    return [_read(d) for d in service.list_documents(db, user.id)]


@router.get("/{document_id}")
def get_document(document_id: str, user: CurrentUser, db: DbSession):
    doc = service.get_document(db, user.id, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return _read(doc, preview=True)


@router.patch("/{document_id}")
def update_document(document_id: str, data: DocumentUpdate, user: CurrentUser, db: DbSession):
    """Share with the team or make private again; rename. Both reversible."""
    doc = service.get_document(db, user.id, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    if data.shared is not None:
        doc.shared = data.shared
    if data.filename is not None:
        doc.filename = service.clean_filename(data.filename)
    db.flush()
    return _read(doc)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, user: CurrentUser, db: DbSession):
    doc = service.get_document(db, user.id, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    db.delete(doc)
