from app.presentation.handlers import build_router
from tests.conftest import make_settings


def test_build_router_returns_router():
    router = build_router(service=None, ollama=None, cloud=None, benchmark=None,
                          store=None, settings=make_settings())
    assert router is not None
