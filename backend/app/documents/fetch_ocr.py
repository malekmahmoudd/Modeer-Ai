"""Download Tesseract's Arabic and English data at a pinned release and verify it.

    python -m app.documents.fetch_ocr [target_dir]

The "best" (LSTM, most accurate) models from tesseract-ocr/tessdata_best 4.1.0,
Apache-2.0. Each file is checked against the SHA-256 recorded here; a mismatch
deletes it and fails. The server never downloads anything.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import httpx

RELEASE = "4.1.0"
FILES = {
    "ara.traineddata": "ab9d157d8e38ca00e7e39c7d5363a5239e053f5b0dbdb3167dde9d8124335896",
    "eng.traineddata": "8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba",
}


def default_dir() -> Path:
    """backend/models/tessdata, for local development."""
    return Path(__file__).resolve().parents[2] / "models" / "tessdata"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        path = target / name
        if path.is_file() and _sha256(path) == expected:
            print(f"{name}: already present and verified")
            continue
        url = f"https://github.com/tesseract-ocr/tessdata_best/raw/{RELEASE}/{name}"
        with httpx.stream("GET", url, follow_redirects=True, timeout=600) as response:
            response.raise_for_status()
            with path.open("wb") as f:
                for block in response.iter_bytes(1 << 20):
                    f.write(block)
        actual = _sha256(path)
        if actual != expected:
            path.unlink()
            raise SystemExit(f"{name}: checksum mismatch ({actual}); deleted")
        print(f"{name}: downloaded and verified")


if __name__ == "__main__":
    fetch(Path(sys.argv[1]) if len(sys.argv) > 1 else default_dir())
