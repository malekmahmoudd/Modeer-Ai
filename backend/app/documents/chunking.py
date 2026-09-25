"""Split extracted text into passages an agent can be given a few of.

About 1,400 characters each (~350 tokens), cut on paragraph and sentence
boundaries, with a short overlap so a sentence that straddles two chunks is
whole in at least one. Each chunk remembers its page and the heading above it,
which is what a citation points to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.documents.parse import Page

TARGET = 1400
OVERLAP = 200
MAX_CHUNKS = 400
_HEADING = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?؟。])\s+")


@dataclass(slots=True)
class Chunk:
    page: int | None
    heading: str | None
    text: str


def _pieces(paragraph: str) -> list[str]:
    """A paragraph small enough to fit, or cut at sentence ends (hard-cut last)."""
    if len(paragraph) <= TARGET:
        return [paragraph]
    out, current = [], ""
    for sentence in _SENTENCE_END.split(paragraph):
        while len(sentence) > TARGET:
            out.append(sentence[:TARGET])
            sentence = sentence[TARGET - OVERLAP :]
        if current and len(current) + 1 + len(sentence) > TARGET:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current)
    return out


def _tail(text: str) -> str:
    """The last ~OVERLAP characters, starting at a word."""
    if len(text) <= OVERLAP:
        return text
    tail = text[-OVERLAP:]
    return tail[tail.find(" ") + 1 :] if " " in tail else tail


def chunk_pages(pages: list[Page]) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading: str | None = None
    for page in pages:
        current = ""
        for paragraph in re.split(r"\n\s*\n", page.text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if match := _HEADING.match(paragraph.splitlines()[0]):
                if current:
                    chunks.append(Chunk(page.number, heading, current))
                    current = ""
                heading = match.group(1)[:200]
                rest = "\n".join(paragraph.splitlines()[1:]).strip()
                if not rest:
                    continue
                paragraph = rest
            for piece in _pieces(paragraph):
                if current and len(current) + 2 + len(piece) > TARGET:
                    chunks.append(Chunk(page.number, heading, current))
                    current = _tail(current) + "\n\n" + piece
                else:
                    current = f"{current}\n\n{piece}".strip()
        if current:
            chunks.append(Chunk(page.number, heading, current))
        if len(chunks) >= MAX_CHUNKS:
            break
    return chunks[:MAX_CHUNKS]
