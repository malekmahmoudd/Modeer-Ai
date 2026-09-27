"""Web Push, standard library plus ``cryptography``: VAPID (RFC 8292) and
message encryption (RFC 8291, aes128gcm, RFC 8188).

The browser gives us an endpoint on its push service and two keys; we sign a
short token proving who we are and encrypt the message so only that browser
can read it. The push service sees neither the text nor who it is about.
"""

from __future__ import annotations

import base64
import json
import os
import struct
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hmac import HMAC

#: Push services a subscription may point at. Anything else is refused, so a
#: stored "endpoint" can never make the server call an address of someone's
#: choosing.
PUSH_HOSTS = (
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "web.push.apple.com",
    "push.apple.com",
    "notify.windows.com",
)
RECORD_SIZE = 4096


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def allowed_endpoint(endpoint: str) -> bool:
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(
        host == known or host.endswith("." + known) for known in PUSH_HOSTS
    )


# --- keys -----------------------------------------------------------------------------


def new_private_key() -> str:
    """A fresh VAPID key, as base64url of the 32-byte private number."""
    key = ec.generate_private_key(ec.SECP256R1())
    return b64url(key.private_numbers().private_value.to_bytes(32, "big"))


def _private(key: str) -> ec.EllipticCurvePrivateKey:
    return ec.derive_private_key(int.from_bytes(unb64url(key), "big"), ec.SECP256R1())


def _raw_public(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )


def public_key(private_key: str) -> str:
    """The browser's ``applicationServerKey``: base64url, uncompressed point."""
    return b64url(_raw_public(_private(private_key).public_key()))


# --- VAPID ----------------------------------------------------------------------------


def vapid_header(endpoint: str, private_key: str, subject: str, *, now: float | None = None) -> str:
    """``Authorization: vapid t=<ES256 JWT>, k=<public key>`` for this endpoint."""
    parts = urlsplit(endpoint)
    claims = {
        "aud": f"{parts.scheme}://{parts.netloc}",
        "exp": int((now or time.time()) + 12 * 3600),
        "sub": subject,
    }
    header = b64url(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    body = b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}".encode()
    der = _private(private_key).sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    signature = b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={header}.{body}.{signature}, k={public_key(private_key)}"


# --- encryption (RFC 8291) ------------------------------------------------------------


def _hmac(key: bytes, data: bytes) -> bytes:
    mac = HMAC(key, hashes.SHA256())
    mac.update(data)
    return mac.finalize()


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    prk = _hmac(salt, ikm)
    return _hmac(prk, info + b"\x01")[:length]


def encrypt(
    plaintext: bytes,
    ua_public: bytes,
    auth_secret: bytes,
    *,
    sender_key: ec.EllipticCurvePrivateKey | None = None,
    salt: bytes | None = None,
) -> bytes:
    """One aes128gcm record: salt, record size, the sender's public key, then the
    ciphertext. ``sender_key`` and ``salt`` are fresh each time unless a test
    pins them."""
    sender = sender_key or ec.generate_private_key(ec.SECP256R1())
    salt = salt or os.urandom(16)
    as_public = _raw_public(sender.public_key())
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    shared = sender.exchange(ec.ECDH(), peer)
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    record = plaintext + b"\x02"  # the last (and only) record
    if len(record) + 16 > RECORD_SIZE:
        raise ValueError("push message too long")
    ciphertext = AESGCM(cek).encrypt(nonce, record, None)
    header = salt + struct.pack(">I", RECORD_SIZE) + bytes([len(as_public)]) + as_public
    return header + ciphertext


def decrypt(body: bytes, ua_private: ec.EllipticCurvePrivateKey, auth_secret: bytes) -> bytes:
    """What the browser does; used by the tests to check a real round trip."""
    salt, keylen = body[:16], body[20]
    as_public = body[21 : 21 + keylen]
    ciphertext = body[21 + keylen :]
    ua_public = _raw_public(ua_private.public_key())
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
    shared = ua_private.exchange(ec.ECDH(), peer)
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    record = AESGCM(cek).decrypt(nonce, ciphertext, None)
    return record.rstrip(b"\x00")[:-1]  # drop padding, then the delimiter
