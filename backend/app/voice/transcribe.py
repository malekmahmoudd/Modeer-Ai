"""Speech to text for the mic button.

The browser records a short clip (at most a minute) and posts it here; it goes
to Groq's Whisper endpoint and the text comes back for the person to check and
edit before sending. The audio is held in memory for the one request and never
written anywhere.
"""

from __future__ import annotations

import logging
from contextlib import suppress

import httpx

from app.core.config import settings
from app.llm.openai_compat_provider import _DEFAULT_BASE, _retry_after

logger = logging.getLogger(__name__)

#: What browsers record: Chrome and Firefox webm/ogg with Opus, Safari mp4/AAC.
AUDIO_TYPES = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/aac": "m4a",
    "audio/x-m4a": "m4a",
}


class VoiceError(RuntimeError):
    def __init__(self, message: str, status: int = 502, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def available() -> bool:
    return settings.voice_enabled and settings.llm_provider == "groq" and bool(settings.llm_api_key)


def extension_for(content_type: str | None) -> str | None:
    return AUDIO_TYPES.get((content_type or "").split(";")[0].strip().lower())


#: A few everyday words in the chosen dialect steer Whisper toward writing it
#: as spoken rather than as Standard Arabic.
DIALECT_HINTS = {
    "egyptian": "كلام بالعامية المصرية: إزيك، عامل إيه، النهارده، بكرة، عايز، كده.",
    "gulf": "كلام باللهجة الخليجية: شلونك، وايد، باچر، أبغى، زين، الحين.",
    "levantine": "حكي باللهجة الشامية: كيفك، هلق، بكرا، بدي، منيح، شو.",
    "msa": "كلام بالعربية الفصحى.",
}


async def transcribe(
    audio: bytes, content_type: str, *, language: str | None = None, dialect: str | None = None
) -> str:
    """The words in a short clip. ``language`` ("ar", "en") and ``dialect`` are
    hints only."""
    ext = extension_for(content_type)
    if ext is None:
        raise VoiceError("That recording format isn't supported.", 415)
    base = (settings.llm_base_url or _DEFAULT_BASE["groq"]).rstrip("/")
    data = {"model": settings.transcribe_model, "response_format": "json", "temperature": "0"}
    if language in ("ar", "en"):
        data["language"] = language
    if dialect in DIALECT_HINTS and language != "en":
        data["prompt"] = DIALECT_HINTS[dialect]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=30)) as client:
            response = await client.post(
                f"{base}/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                data=data,
                files={"file": (f"clip.{ext}", audio, content_type.split(";")[0])},
            )
    except httpx.HTTPError as exc:
        logger.warning("Transcription request failed: %s", type(exc).__name__)
        raise VoiceError("Couldn't reach the speech service. Please try again.") from exc
    if response.status_code == 429:
        raise VoiceError(
            "Voice input is at its limit for now. Please type, or try again shortly.",
            429,
            _retry_after(response),
        )
    if response.status_code >= 400:
        logger.warning("Transcription failed: status=%s", response.status_code)
        raise VoiceError("Couldn't turn that recording into text. Please try again.")
    return str(response.json().get("text", "")).strip()


# --- natural voices ---------------------------------------------------------------------
# Groq's Orpheus text-to-speech. The account owner has to accept its terms once
# in the Groq console; until then this answers "not available" and the browser
# reads replies with the device's own voices.

TERMS_NEEDED = "Natural voices need to be switched on in the Groq console first."


def speech_available() -> bool:
    return available() and settings.tts_enabled


async def speak(text: str, language: str) -> bytes:
    """WAV audio of ``text``, in Arabic or English."""
    arabic = language == "ar"
    model = settings.tts_model_ar if arabic else settings.tts_model_en
    voice = settings.tts_voice_ar if arabic else settings.tts_voice_en
    base = (settings.llm_base_url or _DEFAULT_BASE["groq"]).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=40)) as client:
            response = await client.post(
                f"{base}/audio/speech",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={"model": model, "voice": voice, "input": text, "response_format": "wav"},
            )
    except httpx.HTTPError as exc:
        raise VoiceError("Couldn't reach the speech service. Please try again.") from exc
    if response.status_code == 429:
        raise VoiceError(
            "Voice input is at its limit for now. Please type, or try again shortly.",
            429,
            _retry_after(response),
        )
    if response.status_code >= 400:
        code = ""
        with suppress(ValueError):
            code = response.json().get("error", {}).get("code", "")
        logger.warning("Speech failed: status=%s code=%s", response.status_code, code)
        if code == "model_terms_required":
            raise VoiceError(TERMS_NEEDED, 503)
        raise VoiceError("Couldn't read that aloud. Please try again.")
    return response.content
