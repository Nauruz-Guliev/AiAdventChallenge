import numpy as np

from chunking import Chunk
from embeddings import FakeEmbedder
from index import Hit, IndexStore


def make_chunks():
    return [
        Chunk("d.md:fixed:0", "d.md", "Doc", "fixed", "fixed", "alpha beta", 0, 2),
        Chunk("d.md:fixed:1", "d.md", "Doc", "fixed", "fixed", "gamma delta", 10, 2),
    ]


def test_index_build_and_metadata():
    store = IndexStore.build(make_chunks(), FakeEmbedder(dim=16), model_name="fake")
    assert store.meta["num_chunks"] == 2
    assert store.meta["embedding_dim"] == 16
    for c in store.chunks:
        assert {"chunk_id", "source", "title", "section", "strategy", "text", "token_count"} <= set(c)


def test_index_save_load_roundtrip(tmp_path):
    store = IndexStore.build(make_chunks(), FakeEmbedder(dim=16), model_name="fake")
    p = tmp_path / "idx.json"
    store.save(p)
    loaded = IndexStore.load(p)
    assert loaded.meta["num_chunks"] == 2
    assert [c["chunk_id"] for c in loaded.chunks] == [c["chunk_id"] for c in store.chunks]
    assert np.allclose(loaded.embeddings, store.embeddings)


def test_index_search_top1():
    chunks = [c.as_dict() for c in make_chunks()]
    embs = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
    store = IndexStore(chunks=chunks, embeddings=embs, meta={"strategy": "fixed"})
    hits = store.search([1, 0, 0], top_k=1)
    assert len(hits) == 1
    assert isinstance(hits[0], Hit)
    assert hits[0].chunk_id == "d.md:fixed:0"


def test_index_search_text():
    store = IndexStore.build(make_chunks(), FakeEmbedder(dim=16), model_name="fake")
    hits = store.search_text("alpha beta", FakeEmbedder(dim=16), top_k=2)
    assert len(hits) == 2
