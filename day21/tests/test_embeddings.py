import numpy as np

from embeddings import FakeEmbedder, get_embedder


def test_fake_embedder_shape_and_norm():
    e = FakeEmbedder(dim=32)
    v = e.embed(["hello", "world"])
    assert v.shape == (2, 32)
    norms = np.linalg.norm(v, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_fake_embedder_deterministic():
    e = FakeEmbedder(dim=16)
    a = e.embed(["same text"])[0]
    b = e.embed(["same text"])[0]
    assert np.allclose(a, b)
    c = e.embed(["other text"])[0]
    assert not np.allclose(a, c)


def test_fake_embedder_empty():
    e = FakeEmbedder(dim=8)
    assert e.embed([]).shape == (0, 8)


def test_get_embedder_fake():
    e = get_embedder("fake", dim=24)
    assert isinstance(e, FakeEmbedder)
    assert e.dim == 24


def test_get_embedder_unknown():
    import pytest

    with pytest.raises(ValueError):
        get_embedder("nope")
