"""Text from users and models, made safe to place inside a prompt.

Stored facts, titles, notes and summaries go into the system prompt between
markers like <<PERSONAL_CONTEXT>>. A value that itself contains
"<</PERSONAL_CONTEXT>>" or a line starting "## Rules" would end its block early
and read as instructions. Every such string passes through :func:`as_data`.
"""

from __future__ import annotations

import re

_HEADING = re.compile(r"^\s*#+\s*", re.M)


def as_data(text: str | None, *, single_line: bool = True) -> str:
    """``text`` with block markers defused and no line that reads as a heading."""
    text = (text or "").replace("<<", "‹‹").replace(">>", "››")
    text = _HEADING.sub("", text)
    if single_line:
        text = " ".join(text.split())
    return text
