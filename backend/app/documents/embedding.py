"""Local text embeddings: multilingual-e5-small (MIT), int8, on the CPU.

No third-party API: document text never leaves the server to be embedded.
The model is baked into the image at a pinned revision and checked against a
SHA-256 at build time (see backend/Dockerfile); it is never downloaded while the
server runs. Without it — a development machine that skipped the download, or a
deployment that turns it off — retrieval falls back to keyword search alone,
which still works, just less well across wordings and languages.

e5 expects a "query: " or "passage: " prefix; vectors are mean-pooled and
L2-normalised, so a dot product is the cosine similarity.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path

from app.core.config import settings

#: Identifies the vector space. Stored on every document, so a change of model
#: can never mix vectors from two models in one search.
MODEL_ID = "intfloat/multilingual-e5-small@614241f;qint8"
DIMENSIONS = 384
_BATCH = 16
_MAX_TOKENS = 512


class Embedder:
    def __init__(self, directory: Path) -> None:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self._np = np
        self._tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self._tokenizer.enable_truncation(_MAX_TOKENS)
        self._tokenizer.enable_padding()
        options = ort.SessionOptions()
        # Two threads: embedding must not take every core from the chat server.
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(directory / "model.onnx"), options, providers=["CPUExecutionProvider"]
        )
        self._inputs = {i.name for i in self._session.get_inputs()}
        self._lock = threading.Lock()  # one inference at a time on the shared session

    def _embed(self, texts: list[str]):
        np = self._np
        vectors = []
        for start in range(0, len(texts), _BATCH):
            batch = self._tokenizer.encode_batch(texts[start : start + _BATCH])
            ids = np.array([e.ids for e in batch], dtype=np.int64)
            mask = np.array([e.attention_mask for e in batch], dtype=np.int64)
            feeds = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feeds["token_type_ids"] = np.zeros_like(ids)
            with self._lock:
                hidden = self._session.run(None, feeds)[0]
            pooled = (hidden * mask[..., None]).sum(1) / np.maximum(mask.sum(1, keepdims=True), 1)
            vectors.append(pooled / np.linalg.norm(pooled, axis=1, keepdims=True))
        return np.vstack(vectors).astype(np.float32) if vectors else np.zeros((0, DIMENSIONS))

    def passages(self, texts: list[str]):
        return self._embed([f"passage: {t}" for t in texts])

    def query(self, text: str):
        return self._embed([f"query: {text}"])[0]


@lru_cache(maxsize=1)
def _load(directory: str) -> Embedder | None:
    path = Path(directory)
    if directory and not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path  # relative to the backend root
    files = (path / "model.onnx", path / "tokenizer.json")
    if not directory or not all(f.is_file() for f in files):
        return None
    try:
        return Embedder(path)
    except ImportError:
        return None  # the optional runtime is not installed: keyword search only


def get_embedder() -> Embedder | None:
    """The shared embedder, loaded on first use, or None when unavailable."""
    return _load(settings.embedding_model_dir)


def to_bytes(vector) -> bytes:
    return vector.astype("float32").tobytes()


def from_bytes(blob: bytes):
    import numpy as np

    return np.frombuffer(blob, dtype=np.float32)
