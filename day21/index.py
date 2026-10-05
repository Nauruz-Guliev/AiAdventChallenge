from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import numpy as np

from chunking import Chunk
from embeddings import Embedder


@dataclass
class Hit:
    chunk_id: str
    source: str
    title: str
    section: str
    score: float
    text: str

    def as_dict(self) -> dict:
        return asdict(self)


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


class IndexStore:
    def __init__(self, chunks: list[dict], embeddings: np.ndarray, meta: dict):
        self.chunks = chunks
        self.embeddings = np.asarray(embeddings, dtype=np.float32)
        self.meta = meta

    @classmethod
    def build(cls, chunks: list[Chunk], embedder: Embedder, model_name: str = "unknown") -> "IndexStore":
        texts = [c.text for c in chunks]
        vecs = np.asarray(embedder.embed(texts), dtype=np.float32)
        if vecs.size:
            vecs = _normalize_rows(vecs)
        else:
            vecs = np.zeros((0, getattr(embedder, "dim", 0)), dtype=np.float32)
        meta = {
            "model": model_name,
            "embedding_dim": int(vecs.shape[1]) if vecs.ndim == 2 and vecs.size else 0,
            "num_chunks": len(chunks),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return cls([c.as_dict() for c in chunks], vecs, meta)

    def save(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "meta": self.meta,
            "chunks": [
                {**chunk, "embedding": self.embeddings[i].tolist()}
                for i, chunk in enumerate(self.chunks)
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path) -> "IndexStore":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        chunks: list[dict] = []
        embs: list[list[float]] = []
        for chunk in data["chunks"]:
            chunk = dict(chunk)
            embs.append(chunk.pop("embedding"))
            chunks.append(chunk)
        return cls(chunks, np.asarray(embs, dtype=np.float32), data["meta"])

    def search(self, query_vec: Sequence[float], top_k: int = 5) -> list[Hit]:
        if len(self.chunks) == 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
        n = float(np.linalg.norm(q))
        if n:
            q = q / n
        scores = self.embeddings @ q
        order = np.argsort(-scores)[:top_k]
        hits: list[Hit] = []
        for i in order:
            c = self.chunks[int(i)]
            hits.append(
                Hit(
                    chunk_id=c["chunk_id"],
                    source=c["source"],
                    title=c["title"],
                    section=c["section"],
                    score=float(scores[int(i)]),
                    text=c["text"],
                )
            )
        return hits

    def search_text(self, query: str, embedder: Embedder, top_k: int = 5) -> list[Hit]:
        vec = embedder.embed([query])[0]
        return self.search(vec, top_k=top_k)
