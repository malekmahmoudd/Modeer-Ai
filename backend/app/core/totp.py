"""Time-based one-time codes (RFC 6238), as authenticator apps make them.

Standard library only: HMAC-SHA1 over a 30-second counter, 6 digits — what
Google Authenticator, Microsoft Authenticator, 1Password, Aegis and the rest
expect by default. Checked against the RFC's own test vectors.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6
#: Steps either side of now that still count: phone clocks drift.
WINDOW = 1
ISSUER = "Fareeq"


def new_secret() -> str:
    """160 random bits, base32 without padding (what the apps accept)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def code_at(secret: str, step: int, *, digits: int = DIGITS, digest=hashlib.sha1) -> str:
    mac = hmac.new(_key(secret), struct.pack(">Q", step), digest).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def verify(
    secret: str, code: str, *, last_step: int | None = None, now: float | None = None
) -> int | None:
    """The step a code belongs to, or None. A step at or before ``last_step`` is
    refused, so a code seen over someone's shoulder cannot be used twice."""
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != DIGITS:
        return None
    here = current_step(now)
    for step in range(here - WINDOW, here + WINDOW + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str) -> str:
    """The otpauth:// link a QR code carries; tapping it on a phone also works."""
    label = quote(f"{ISSUER}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}&digits={DIGITS}&period={STEP_SECONDS}"
