"""Serve the privacy notice so the app can show it rather than link away.

Deliberately public: someone deciding whether to accept an invitation needs to
read what will be stored about them *before* they have an account. Kept as one
markdown file so the text a user reads and the text in the repository cannot
drift apart, and kept inside the backend package so it ships in the image --
the Docker build context is ``backend/``, so a copy under ``docs/`` would be
absent at runtime.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/legal", tags=["legal"])

#: backend/app/api/routes/legal.py -> backend/app/ -> legal/privacy.md
_PRIVACY_PATH = Path(__file__).resolve().parents[2] / "legal" / "privacy.md"


@lru_cache(maxsize=1)
def _privacy_text() -> str:
    return _PRIVACY_PATH.read_text(encoding="utf-8")


@router.get("/privacy")
def privacy() -> dict:
    """The privacy notice, as markdown, for the client to render."""
    try:
        return {"format": "markdown", "document": "privacy", "content": _privacy_text()}
    except OSError as exc:  # pragma: no cover - only when the file is missing
        raise HTTPException(status_code=404, detail="Privacy notice is unavailable") from exc
