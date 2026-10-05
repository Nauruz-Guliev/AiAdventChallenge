import numpy as np

from app.infrastructure.embeddings import FakeEmbedder


def test_fake_embedder_deterministic_and_normalized():
    embedder = FakeEmbedder(dim=64)
    a = embedder.embed(["hello"])
    b = embedder.embed(["hello"])
    assert a.shape == (1, 64)
    assert np.allclose(a, b)
    assert np.isclose(float(np.linalg.norm(a[0])), 1.0, atol=1e-5)
