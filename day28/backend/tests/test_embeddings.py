import numpy as np

from app.infrastructure.embeddings import FakeEmbedder, get_embedder


def test_fake_embedder_shape_and_normalized():
    e = FakeEmbedder(dim=8)
    v = e.embed(["hello", "world"])
    assert v.shape == (2, 8)
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)


def test_get_embedder_unknown():
    import pytest

    with pytest.raises(ValueError):
        get_embedder("nope")
