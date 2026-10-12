from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.domain.models import Hit, IndexNotFound


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class JsonRetriever:
    def __init__(self, index_path: str | Path, embedder, top_k: int = 4):
        path = Path(index_path)
        if not path.exists():
            raise IndexNotFound(f"Индекс не найден: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        self._chunks = [dict(c) for c in data["chunks"]]
        matrix = np.asarray([c.pop("embedding") for c in self._chunks], dtype=np.float32)
        self._embeddings = _normalize_rows(matrix).astype(np.float32)
        self._embedder = embedder
        self.top_k = top_k
        self._chunk_index = {c["chunk_id"]: i for i, c in enumerate(self._chunks)}

    def chunk_count(self) -> int:
        return len(self._chunks)

    def similarity(self, text: str, chunk_id: str) -> float:
        idx = self._chunk_index.get(chunk_id)
        if idx is None:
            return 0.0
        q = np.asarray(self._embedder.embed([text])[0], dtype=np.float32)
        n = float(np.linalg.norm(q))
        if n:
            q = q / n
        return float(self._embeddings[idx] @ q)

    def search(self, question: str, top_k: int | None = None) -> list[Hit]:
        k = top_k or self.top_k
        if not self._chunks:
            return []
        q = np.asarray(self._embedder.embed([question])[0], dtype=np.float32)
        n = float(np.linalg.norm(q))
        if n:
            q = q / n
        scores = self._embeddings @ q
        order = np.argsort(-scores)[:k]
        hits: list[Hit] = []
        for i in order:
            c = self._chunks[int(i)]
            hits.append(Hit(
                chunk_id=c["chunk_id"],
                source=c["source"],
                title=c["title"],
                section=c["section"],
                score=float(scores[int(i)]),
                text=c["text"],
            ))
        return hits
