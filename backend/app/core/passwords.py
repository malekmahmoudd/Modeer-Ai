"""Passwords and recovery codes. Standard library only.

Passwords are stored as scrypt hashes — deliberately slow and memory-hard, so a
stolen database does not turn into a list of passwords overnight. Recovery
codes are long random strings, so a fast hash is enough for them; what protects
them is their length and the attempt throttle in front of every check.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

# ~16 MB and a few tens of milliseconds per check: noticeable to an attacker
# guessing millions of passwords, not to a person signing in.
_N, _R, _P, _DKLEN = 2**14, 8, 1, 32
_SCHEME = "scrypt"

MIN_PASSWORD = 10
MAX_PASSWORD = 128

RECOVERY_CODE_COUNT = 10
# No 0/O or 1/I/L: these get read off a screen or a sheet of paper.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"{_SCHEME}${_N}${_R}${_P}${salt.hex()}${derived.hex()}"


# Verified against when the account does not exist or has no password, so a
# wrong email takes as long as a wrong password and reveals nothing by timing.
_DECOY = hash_password(secrets.token_urlsafe(16))


def verify_password(password: str, stored: str | None) -> bool:
    """True only for the right password. Takes the same time either way."""
    candidate = stored or _DECOY
    try:
        scheme, n, r, p, salt, expected = candidate.split("$")
        if scheme != _SCHEME:
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected) // 2,
        )
    except (ValueError, TypeError):
        return False
    return stored is not None and hmac.compare_digest(derived.hex(), expected)


def new_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Readable single-use codes, like ``7KXQ-M4RT-9WHE``: about 60 bits each."""
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(12))
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:]}")
    return codes


def normalise_code(code: str) -> str:
    """Forgiving about how a code is typed: case, spaces and dashes do not matter."""
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(normalise_code(code).encode("utf-8")).hexdigest()


def password_problem(password: str) -> str | None:
    """A reason the password is not acceptable, in words a person can act on."""
    if len(password) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if len(password) > MAX_PASSWORD:
        return f"Use at most {MAX_PASSWORD} characters."
    if not password.strip():
        return "A password cannot be only spaces."
    return None
