"""Download the embedding model at a pinned revision and verify it.

    python -m app.documents.fetch_model [target_dir]

Used by the Dockerfile at build time and by developers once. Each file is
checked against a SHA-256 recorded here; a mismatch deletes the file and fails,
so an image can never ship a model other than the one reviewed. The server
itself never downloads anything.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import httpx

REPO = "intfloat/multilingual-e5-small"  # MIT licence
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
FILES = {
    # local name: (path in the repository, sha256)
    "model.onnx": (
        "onnx/model_qint8_avx512_vnni.onnx",
        "dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88",
    ),
    "tokenizer.json": (
        "tokenizer.json",
        "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
    ),
}
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "models" / "multilingual-e5-small"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(target: Path = DEFAULT_DIR) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name, (remote, expected) in FILES.items():
        path = target / name
        if path.is_file() and _sha256(path) == expected:
            print(f"{name}: already present and verified")
            continue
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{remote}"
        with httpx.stream("GET", url, follow_redirects=True, timeout=600) as response:
            response.raise_for_status()
            with path.open("wb") as f:
                for block in response.iter_bytes(1 << 20):
                    f.write(block)
        actual = _sha256(path)
        if actual != expected:
            path.unlink()
            raise SystemExit(f"{name}: checksum mismatch ({actual}); refusing to keep it")
        print(f"{name}: downloaded and verified")


if __name__ == "__main__":
    fetch(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR)
