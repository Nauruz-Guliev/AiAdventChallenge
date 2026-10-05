from embeddings import FakeEmbedder
from pipeline import build_index, load_corpus


def write_corpus(tmp_path):
    (tmp_path / "a.md").write_text(
        "# Alpha\n\nSome text about alpha.\n\n## Sub\n\nMore alpha text.", encoding="utf-8"
    )
    (tmp_path / "b.md").write_text("# Beta\n\nBeta content here.", encoding="utf-8")


def test_load_corpus(tmp_path):
    write_corpus(tmp_path)
    docs = load_corpus(tmp_path)
    assert [d.source for d in docs] == ["a.md", "b.md"]
    assert docs[0].title == "Alpha"


def test_build_index_both_strategies(tmp_path):
    write_corpus(tmp_path)
    out = tmp_path / "index"
    e = FakeEmbedder(dim=16)
    store_f, path_f = build_index(tmp_path, "fixed", e, out, model_name="fake")
    store_s, path_s = build_index(tmp_path, "structure", e, out, model_name="fake")
    assert path_f.exists() and path_s.exists()
    assert store_f.meta["strategy"] == "fixed"
    assert store_s.meta["strategy"] == "structure"
    assert store_f.meta["num_chunks"] >= 1


def test_build_index_unknown_strategy(tmp_path):
    import pytest

    write_corpus(tmp_path)
    with pytest.raises(ValueError):
        build_index(tmp_path, "nope", FakeEmbedder(dim=8), tmp_path / "index")
