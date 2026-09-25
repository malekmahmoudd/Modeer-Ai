"""Measure retrieval on the labelled set in app/documents/evalset. No LLM calls.

    python -m app.documents.evaluate            # keyword, and hybrid if the model is present
    python -m app.documents.evaluate --sweep    # also try similarity thresholds

For each answerable question: did the returned passages contain the answer
(recall), and how high was the first passage that did (MRR)? For each
unanswerable one: was nothing returned (the gate held)? Run with whole-document
mode off too, which measures section ranking rather than document choice.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Document, DocumentChunk, User
from app.documents import embedding as emb
from app.documents import retrieval
from app.documents.chunking import chunk_pages
from app.documents.parse import Page

SET = Path(__file__).parent / "evalset"


def _database(embedder):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(email="eval@local", display_name="Eval")
    db.add(user)
    db.flush()
    for path in sorted(SET.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        chunks = chunk_pages([Page(None, text)])
        vectors = embedder.passages([c.text for c in chunks]) if embedder else None
        doc = Document(
            user_id=user.id,
            agent_id="modeer",
            shared=True,
            filename=path.name,
            kind="md",
            size_bytes=len(text),
            sha256="-",
            status="ready",
            chars=sum(len(c.text) for c in chunks),
            embed_model=emb.MODEL_ID if embedder else None,
        )
        doc.chunks = [
            DocumentChunk(
                position=i,
                heading=c.heading,
                text=c.text,
                embedding=emb.to_bytes(vectors[i]) if embedder else None,
            )
            for i, c in enumerate(chunks)
        ]
        db.add(doc)
    db.commit()
    return db, user


def run(*, embedder=None, whole_doc=True, min_similarity=None) -> dict:
    questions = json.loads((SET / "questions.json").read_text(encoding="utf-8"))
    db, user = _database(embedder)

    def ask(q):
        vector = embedder.query(q) if embedder else None
        return retrieval.retrieve(
            db,
            user.id,
            agent_id="study",
            is_leo=False,
            private_ok=True,
            message=q,
            query_vector=vector,
            whole_doc=whole_doc,
            min_similarity=min_similarity,
        )

    found, reciprocal, empty, misses = 0, 0.0, 0, []
    for item in questions["answerable"]:
        hits = ask(item["q"])
        if not hits:
            empty += 1
        rank = next(
            (i for i, h in enumerate(hits, 1) if item["snippet"].casefold() in h.text.casefold()),
            None,
        )
        if rank:
            found += 1
            reciprocal += 1 / rank
        else:
            misses.append(item["q"])
    leaked = [q for q in questions["unanswerable"] if ask(q)]
    n = len(questions["answerable"])
    return {
        "recall": round(found / n, 3),
        "mrr": round(reciprocal / n, 3),
        "answerable_with_nothing": empty,
        "unanswerable_that_retrieved": len(leaked),
        "misses": misses,
        "leaked": leaked,
    }


def main() -> None:
    embedder = emb.get_embedder()
    modes = [("keyword", None)] + ([("hybrid", embedder)] if embedder else [])
    if not embedder:
        print("(no embedding model found: keyword search only)")
    for name, e in modes:
        for whole in (True, False):
            r = run(embedder=e, whole_doc=whole)
            print(
                f"{name:8} whole_doc={whole!s:5} recall={r['recall']} mrr={r['mrr']} "
                f"empty={r['answerable_with_nothing']} leaked={r['unanswerable_that_retrieved']}"
            )
    if embedder and "--sweep" in sys.argv:
        for t in (0.78, 0.80, 0.82, 0.84, 0.86):
            r = run(embedder=embedder, whole_doc=False, min_similarity=t)
            print(
                f"threshold={t} recall={r['recall']} empty={r['answerable_with_nothing']} "
                f"leaked={r['unanswerable_that_retrieved']}"
            )
    if "-v" in sys.argv:
        r = run(embedder=embedder, whole_doc=False)
        print("misses:", *r["misses"], sep="\n  ")
        print("leaked:", *r["leaked"], sep="\n  ")


if __name__ == "__main__":
    main()
