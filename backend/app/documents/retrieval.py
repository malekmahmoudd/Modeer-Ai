"""Find the passages of the person's documents that answer this message.

Two rankings are fused (reciprocal rank fusion): BM25 keyword scores, which
catch names, model numbers and rare words, and cosine similarity from the local
embedding model, which catches the same meaning in other words or another
language. At most a few thousand chunks per person, so both are computed in
plain Python/numpy — no vector index is needed at this size.

Retrieval is gated. Passages are added only when one is actually relevant
(high similarity, or a real keyword match), or when the person refers to their
files. Most turns get nothing, and pay nothing.

Visibility is part of the query: an agent sees documents given to it, plus the
ones shared with the team; Leo retrieves only shared ones; a turn without
private notes (Ask My Team) sees shared ones only.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import Document
from app.documents import embedding as emb
from app.memory.sensitivity import _fold

#: Words that mean "my files", in English and Arabic.
_REFERS_TO_FILES = re.compile(
    r"\b(documents?|docs?|files?|pdfs?|cv|résumé|resume|syllabus|notes|attachment|uploaded|"
    r"upload|report|paper|manual|contract|brief|spec|sheet|thread|itinerary|booking)\b"
    r"|(?:ملف|الملف|مستند|المستند|السيره|المرفق|الوثيقه)",
    re.I,
)
_TOKEN = re.compile(r"\w+", re.UNICODE)
_STOP = frozenset(
    "a an and are as at be but by can could did do does for from had has have how i if in "
    "is it its me my of on or our so than that the their them then there these they this "
    "to was we were what when where which who why will with would you your about into "
    "في من على الى عن مع هذا هذه ذلك التي الذي ما ماذا كيف هل انا انت هو هي".split()
)
_K1, _B = 1.5, 0.75
_RRF_K = 60
#: A document this short is given whole when it is relevant: summaries and
#: "what does my CV say" need all of it, and top-k passages would miss parts.
_WHOLE_DOC_CHARS = 3000
MAX_HITS = 4


@dataclass(slots=True)
class Hit:
    label: str  # D1, D2 …
    document_id: str
    filename: str
    page: int | None
    heading: str | None
    text: str
    score: float


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(_fold(text).casefold()) if len(t) > 1 and t not in _STOP]


def visible_documents(
    db: Session, user_id: str, *, agent_id: str, is_leo: bool, private_ok: bool
) -> list[Document]:
    """Ready documents this agent may read. Enforced in SQL, not by filtering."""
    stmt = select(Document).where(Document.user_id == user_id, Document.status == "ready")
    if is_leo or not private_ok:
        stmt = stmt.where(Document.shared.is_(True))
    else:
        stmt = stmt.where(or_(Document.agent_id == agent_id, Document.shared.is_(True)))
    return list(db.scalars(stmt.options(selectinload(Document.chunks))))


def _bm25(query: list[str], docs: list[list[str]]) -> list[float]:
    if not docs or not query:
        return [0.0] * len(docs)
    n = len(docs)
    avg = sum(len(d) for d in docs) / n or 1.0
    df = Counter(term for d in docs for term in set(d))
    scores = []
    for d in docs:
        tf = Counter(d)
        score = 0.0
        for term in set(query):
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            f = tf[term]
            score += idf * f * (_K1 + 1) / (f + _K1 * (1 - _B + _B * len(d) / avg))
        scores.append(score)
    return scores


def _ranks(scores: list[float]) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    ranks = [0] * len(scores)
    for rank, i in enumerate(order, 1):
        ranks[i] = rank
    return ranks


def retrieve(
    db: Session,
    user_id: str,
    *,
    agent_id: str,
    is_leo: bool,
    private_ok: bool,
    message: str,
    previous: str = "",
    query_vector=None,
    whole_doc: bool = True,
    min_similarity: float | None = None,
) -> list[Hit]:
    """The passages to add to this turn, best first; [] when none is relevant.

    ``query_vector`` is the embedded query (see :func:`query_text`), computed by
    the caller off the event loop; None means keyword search only.
    """
    documents = visible_documents(
        db, user_id, agent_id=agent_id, is_leo=is_leo, private_ok=private_ok
    )
    chunks = [(doc, chunk) for doc in documents for chunk in doc.chunks]
    if not chunks:
        return []

    # The previous message helps a follow-up ("and section 3?") find its topic.
    query_tokens = _tokens(message) + _tokens(previous)[:20]
    chunk_tokens = [_tokens(f"{c.heading or ''} {c.text}") for _, c in chunks]
    keyword = _bm25(query_tokens, chunk_tokens)
    own_terms = set(_tokens(message))
    matched = [len(own_terms & set(toks)) for toks in chunk_tokens]

    similarity = [0.0] * len(chunks)
    if query_vector is not None:
        for i, (doc, chunk) in enumerate(chunks):
            if chunk.embedding is not None and doc.embed_model == emb.MODEL_ID:
                similarity[i] = float(emb.from_bytes(chunk.embedding) @ query_vector)

    names = {_fold(d.filename).casefold() for d in documents}
    refers = bool(_REFERS_TO_FILES.search(_fold(message))) or any(
        stem and stem in _fold(message).casefold()
        for stem in (n.rsplit(".", 1)[0] for n in names)
        if len(stem) > 3
    )
    # Is anything here about this message? e5 scores sit in a narrow band
    # (unrelated text still scores ~0.78), so a high score counts on its own and
    # a middling one only when it stands out from the rest of their files.
    # Calibrated on app/documents/evalset (python -m app.documents.evaluate).
    hard = settings.rag_min_similarity if min_similarity is None else min_similarity
    soft = settings.rag_soft_similarity
    top = max(similarity) if query_vector is not None else 0.0
    typical = sorted(similarity)[len(similarity) // 2]
    about_files = (
        top >= hard
        or (top >= soft and top - typical >= settings.rag_similarity_margin)
        or max(matched) >= 2
    )
    if not about_files and not refers:
        return []
    relevant = [similarity[i] >= soft or matched[i] >= 2 for i in range(len(chunks))]

    fused = [
        1 / (_RRF_K + a) + (1 / (_RRF_K + b) if query_vector is not None else 0.0)
        for a, b in zip(_ranks(keyword), _ranks(similarity), strict=True)
    ]
    order = sorted(range(len(chunks)), key=lambda i: -fused[i])
    if not refers:
        order = [i for i in order if relevant[i]] or order[:1]

    # "Summarise my CV": when they point at a file and it is short, it is given
    # whole — top passages would miss parts. Otherwise the best passages win.
    best_doc = chunks[order[0]][0] if order else None
    whole = whole_doc and refers and best_doc is not None and best_doc.chars <= _WHOLE_DOC_CHARS
    if whole:
        order = [i for i, (d, _) in enumerate(chunks) if d.id == best_doc.id]

    hits: list[Hit] = []
    budget = settings.rag_context_chars
    for i in order:
        doc, chunk = chunks[i]
        # A whole short document is all of it, however many sections it has.
        if (len(hits) >= MAX_HITS and not whole) or (hits and len(chunk.text) > budget):
            break
        text = chunk.text[:budget]  # only the first passage can be cut to fit
        budget -= len(text)
        hits.append(
            Hit(
                label=f"D{len(hits) + 1}",
                document_id=doc.id,
                filename=doc.filename,
                page=chunk.page,
                heading=chunk.heading,
                text=text,
                score=round(fused[i], 4),
            )
        )
    return hits


def query_text(message: str, previous: str = "") -> str:
    """What is embedded for the search: this message, led by the end of the last."""
    return f"{previous[-300:]} {message}".strip()


def file_index(db: Session, user_id: str, *, agent_id: str, is_leo: bool) -> list[str]:
    """What the agent is told it has, by name: its own and shared files; for Leo,
    everything, with the teammate it belongs to (names that look sensitive are
    not shown)."""
    from app.agents.registry import get_agent
    from app.memory.sensitivity import looks_sensitive

    stmt = select(Document).where(Document.user_id == user_id, Document.status == "ready")
    if not is_leo:
        stmt = stmt.where(or_(Document.agent_id == agent_id, Document.shared.is_(True)))
    lines = []
    for doc in db.scalars(stmt.order_by(Document.created_at).limit(20)):
        name = "(a private file)" if looks_sensitive(doc.filename) else doc.filename
        owner = get_agent(doc.agent_id)
        holder = owner.name if owner else doc.agent_id
        lines.append(f"{name} ({'shared with the team' if doc.shared else 'with ' + holder})")
    return lines
