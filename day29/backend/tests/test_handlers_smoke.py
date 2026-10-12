from app.presentation.handlers import build_router
from tests.conftest import make_settings


def test_build_router_returns_router():
    router = build_router(
        service=None,
        ollama=None,
        cloud=None,
        benchmark=None,
        ab_runner=None,
        store=None,
        settings=make_settings(),
    )
    assert router is not None


def test_build_router_registers_commands():
    router = build_router(
        service=None, ollama=None, cloud=None, benchmark=None, ab_runner=None, store=None,
        settings=make_settings(),
    )
    names = set()
    for observer in router.message.handlers:
        for flt in observer.filters:
            cmd = getattr(flt.callback, "commands", None)
            if cmd:
                names.update(getattr(cmd, "commands", cmd))
    assert {"start", "help", "profile", "quant", "ab", "eval"} <= names
