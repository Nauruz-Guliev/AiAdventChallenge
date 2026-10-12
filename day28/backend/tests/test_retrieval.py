import json

from app.infrastructure.embeddings import FakeEmbedder
from app.infrastructure.retrieval import JsonRetriever


def _make_index(path, embedder, texts):
    vecs = embedder.embed(texts)
    chunks = [
        {"chunk_id": f"c{i}", "source": "doc.md", "title": "T", "section": "s",
         "text": t, "embedding": vecs[i].tolist()}
        for i, t in enumerate(texts)
    ]
    path.write_text(json.dumps({"meta": {}, "chunks": chunks}), encoding="utf-8")


def test_search_returns_hits(tmp_path):
    emb = FakeEmbedder(dim=8)
    p = tmp_path / "idx.json"
    _make_index(p, emb, ["alpha beta", "gamma delta"])
    r = JsonRetriever(p, emb, top_k=2)
    assert r.chunk_count() == 2
    hits = r.search("alpha beta", top_k=1)
    assert len(hits) == 1 and hits[0].chunk_id == "c0"
    assert 0.0 <= r.similarity("alpha beta", "c0") <= 1.0
