"""Voice: turn a short recording into text for the message box."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.usage import BudgetExceeded, charge, limited_caller
from app.voice import transcribe as voice

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("")
def voice_status(user: CurrentUser) -> dict:
    """Whether the mic button can work here."""
    return {"transcribe": voice.available(), "max_seconds": 60}


def _daily_voice(caller: Annotated[str | None, Depends(limited_caller)]) -> None:
    """One of today's transcriptions. Charged before the account session opens a
    write of its own, like uploads: SQLite allows one writer at a time."""
    if not voice.available():
        raise HTTPException(503, "Voice input isn't available on this server.")
    try:
        charge(caller or "local-demo", "voice", 1, settings.voice_per_day, 86400)
    except BudgetExceeded as exc:
        raise HTTPException(
            429,
            "That's today's voice limit. You can still type.",
            headers={"Retry-After": str(int(exc.retry_after))},
        ) from exc


@router.post("/transcribe")
async def transcribe(
    _quota: Annotated[None, Depends(_daily_voice)],
    request: Request,
    user: CurrentUser,
    audio: Annotated[UploadFile, File()],
    language: Annotated[str | None, Form()] = None,
) -> dict:
    """The text of one recording. Nothing is stored: not the audio, not the text."""
    declared = int(request.headers.get("content-length") or 0)
    if declared > settings.voice_max_bytes + 64 * 1024:
        raise HTTPException(413, "That recording is too long. Keep it under a minute.")
    data = await audio.read(settings.voice_max_bytes + 1)
    if len(data) > settings.voice_max_bytes:
        raise HTTPException(413, "That recording is too long. Keep it under a minute.")
    if len(data) < 256:
        raise HTTPException(400, "That recording is empty.")
    if voice.extension_for(audio.content_type) is None:
        raise HTTPException(415, "That recording format isn't supported.")
    try:
        text = await voice.transcribe(data, audio.content_type or "", language=language)
    except voice.VoiceError as exc:
        headers = {"Retry-After": str(int(exc.retry_after))} if exc.retry_after else None
        raise HTTPException(exc.status, str(exc), headers=headers) from exc
    return {"text": text}
