from __future__ import annotations

import hashlib
from typing import Sequence

import numpy as np

DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


class Embedder:
    dim: int

    def embed(self, texts: Sequence[str]) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError


class FakeEmbedder(Embedder):
    """Детерминированные нормализованные векторы без модели — для тестов."""

    def __init__(self, dim: int = 64):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        repeat = (self.dim // len(h)) + 1
        raw = np.frombuffer((h * repeat)[: self.dim], dtype=np.uint8).astype(np.float32)
        v = raw - 127.5
        n = float(np.linalg.norm(v))
        return (v / n).astype(np.float32) if n else v

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack([self._vec(t) for t in texts]).astype(np.float32)


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str = DEFAULT_MODEL, batch_size: int = 16):
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dim(self) -> int:
        return int(self._load().get_sentence_embedding_dimension())

    def tokenize(self, text: str) -> list:
        return self._load().tokenize(text)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        model = self._load()
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vecs = model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vecs, dtype=np.float32)


def get_embedder(name: str, model: str | None = None, dim: int = 64) -> Embedder:
    if name == "fake":
        return FakeEmbedder(dim=dim)
    if name == "sentence":
        return SentenceTransformerEmbedder(model or DEFAULT_MODEL)
    raise ValueError(f"unknown embedder: {name!r}")
