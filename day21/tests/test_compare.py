from chunking import Chunk
from compare import DEFAULT_QUERIES, compare_indices, evaluate, strategy_stats
from embeddings import FakeEmbedder
from index import IndexStore
from pipeline import build_index


def test_strategy_stats():
    chunks = [
        Chunk("s:f:0", "s", "T", "fixed", "fixed", "a b c", 0, 3),
        Chunk("s:f:1", "s", "T", "fixed", "fixed", "d e", 8, 2),
    ]
    store = IndexStore.build(chunks, FakeEmbedder(dim=8), model_name="fake")
    stats = strategy_stats(store)
    assert stats["num_chunks"] == 2
    assert stats["avg_tokens"] == 2.5
    assert stats["max_tokens"] == 3


def test_evaluate_shape():
    chunks = [Chunk("a.md:struct:0", "a.md", "A", "A", "structure", "word " * 10, 0, 10)]
    store = IndexStore.build(chunks, FakeEmbedder(dim=8), model_name="fake")
    result = evaluate(store, FakeEmbedder(dim=8), queries=[{"query": "word", "expect": "a.md"}])
    assert result["total"] == 1
    assert 0.0 <= result["hit_rate"] <= 1.0


def test_compare_indices(tmp_path):
    (tmp_path / "a.md").write_text("# A\n\n" + "word " * 50, encoding="utf-8")
    out = tmp_path / "index"
    e = FakeEmbedder(dim=8)
    build_index(tmp_path, "fixed", e, out, model_name="fake")
    build_index(tmp_path, "structure", e, out, model_name="fake")
    report = compare_indices(out, e, queries=[{"query": "word", "expect": "a.md"}], report_dir=tmp_path)
    assert "fixed" in report and "structure" in report
    assert "num_chunks" in report["fixed"]
    assert (tmp_path / "comparison.md").exists()
    assert (tmp_path / "comparison.json").exists()


def test_default_queries_nonempty():
    assert len(DEFAULT_QUERIES) >= 5
