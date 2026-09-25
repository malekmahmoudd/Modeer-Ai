"""Uploading, reading in, and removing documents.

An upload is checked (size, count, real file type), recorded as "processing",
and then read in the background: parsed in a sandboxed child process, split into
chunks, and embedded locally. The file's bytes are discarded after parsing;
only the text is kept. A file with no extractable text — a scanned PDF, since
there is no OCR — fails with a message that says so.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document, DocumentChunk
from app.db.session import SessionLocal
from app.documents import embedding as emb
from app.documents.chunking import chunk_pages
from app.documents.parse import Unsupported, detect_kind, parse_isolated

logger = logging.getLogger(__name__)
#: Fewer characters than this after extraction means there was no real text.
_MIN_CHARS = 40
NO_TEXT = (
    "No text found in this file. Scanned PDFs and photos need OCR, which isn't "
    "supported: upload a file whose text you can select."
)


class Rejected(ValueError):
    """An upload refused before it is stored; ``status`` is the HTTP code."""

    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def clean_filename(name: str) -> str:
    """A display name: no path, no control characters, at most 200 characters."""
    name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    name = re.sub(r"\s+", " ", name).strip().lstrip(".")
    return name[:200] or "document"


def create(
    db: Session, user_id: str, *, agent_id: str, filename: str, data: bytes, shared: bool
) -> Document:
    """Validate an upload and record it; the caller then schedules :func:`ingest`."""
    if not settings.documents_enabled:
        raise Rejected("Document uploads are switched off on this deployment.", 404)
    if len(data) > settings.document_max_bytes:
        mb = settings.document_max_bytes // (1024 * 1024)
        raise Rejected(f"That file is over the {mb} MB limit.", 413)
    if not data:
        raise Rejected("That file is empty.")
    count = db.scalar(select(func.count()).select_from(Document).where(Document.user_id == user_id))
    if count >= settings.documents_per_user:
        raise Rejected(
            f"You can keep up to {settings.documents_per_user} documents. "
            "Delete one to add another.",
            409,
        )
    name = clean_filename(filename)
    try:
        kind = detect_kind(data, name)
    except Unsupported as exc:
        raise Rejected(str(exc), 415) from exc
    doc = Document(
        user_id=user_id,
        agent_id=agent_id,
        # Leo reads shared files only (he briefs the whole team), so a file
        # given to him is a file given to the team.
        shared=shared or agent_id == "modeer",
        filename=name,
        kind=kind,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        status="processing",
    )
    db.add(doc)
    db.flush()
    return doc


async def ingest(document_id: str, data: bytes) -> None:
    """Read a recorded upload in: parse, chunk, embed, store. Never raises."""
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        try:
            pages = await parse_isolated(data, doc.kind, seconds=settings.document_parse_seconds)
            text_chars = sum(len(p.text) for p in pages)
            if text_chars < _MIN_CHARS:
                raise Unsupported(NO_TEXT)
            if text_chars > settings.document_max_chars:
                # Keep the start; say so rather than silently dropping the rest.
                pages = _truncate(pages, settings.document_max_chars)
            chunks = chunk_pages(pages)
            embedder = emb.get_embedder()
            vectors = (
                await asyncio.to_thread(embedder.passages, [c.text for c in chunks])
                if embedder is not None
                else None
            )
            doc.chunks = [
                DocumentChunk(
                    position=i,
                    page=c.page,
                    heading=c.heading,
                    text=c.text,
                    embedding=emb.to_bytes(vectors[i]) if vectors is not None else None,
                )
                for i, c in enumerate(chunks)
            ]
            doc.pages = sum(1 for p in pages if p.number is not None) or 1
            doc.chars = sum(len(c.text) for c in chunks)
            doc.embed_model = emb.MODEL_ID if vectors is not None else None
            doc.status = "ready"
            if text_chars > settings.document_max_chars:
                doc.error = "Only the first part of this file was kept: it is very long."
        except Unsupported as exc:
            doc.status, doc.error = "failed", str(exc)[:300]
        except Exception as exc:  # noqa: BLE001 - a failed upload must not take the server down
            logger.warning("Document ingest failed: %s", type(exc).__name__)
            doc.status, doc.error = "failed", "The file could not be read."
        db.commit()


def _truncate(pages, limit: int):
    kept, used = [], 0
    for page in pages:
        if used >= limit:
            break
        page.text = page.text[: limit - used]
        used += len(page.text)
        kept.append(page)
    return kept


def list_documents(db: Session, user_id: str) -> list[Document]:
    return list(
        db.scalars(
            select(Document).where(Document.user_id == user_id).order_by(Document.created_at)
        )
    )


def get_document(db: Session, user_id: str, document_id: str) -> Document | None:
    return db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
