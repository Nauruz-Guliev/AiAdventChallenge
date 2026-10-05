import json

import pytest

from app.domain.models import IndexNotFound
from app.infrastructure.embeddings import FakeEmbedder
from app.infrastructure.retrieval import JsonRetriever


def make_index(path, chunks):
    path.write_text(json.dumps({"meta": {}, "chunks": chunks}, ensure_ascii=False), encoding="utf-8")


def test_retriever_returns_top_k_and_fields(tmp_path):
    index = tmp_path / "index.json"
    make_index(index, [
        {"chunk_id": "a", "source": "docs/a.md", "title": "A", "section": "Intro",
         "text": "alpha", "embedding": [1.0, 0.0, 0.0]},
        {"chunk_id": "b", "source": "docs/b.md", "title": "B", "section": "Main",
         "text": "beta", "embedding": [0.0, 1.0, 0.0]},
    ])
    retriever = JsonRetriever(index, FakeEmbedder(dim=3), top_k=1)
    assert retriever.chunk_count() == 2
    hits = retriever.search("hello", top_k=2)
    assert len(hits) == 2
    assert {h.chunk_id for h in hits} == {"a", "b"}
    assert all(h.text in {"alpha", "beta"} for h in hits)


def test_retriever_raises_on_missing_index():
    with pytest.raises(IndexNotFound):
        JsonRetriever("nope.json", FakeEmbedder(dim=3))
