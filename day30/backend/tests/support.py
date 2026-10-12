from __future__ import annotations

from app.application.chat_service import ChatService
from app.application.concurrency import OverloadedGuard
from app.application.rate_limit import RateLimiter
from app.config import Settings
from app.domain.models import Completion, ModelInfo, StreamDelta, StreamDone, Usage
from app.infrastructure.metrics import Metrics
from app.presentation.app import create_app


class FakeGateway:
    def __init__(self, *, text: str = "привет", fail_health: bool = False) -> None:
        self.text = text
        self.fail_health = fail_health
        self.requests: list[dict] = []

    async def chat(self, messages, *, model=None, temperature=None, max_tokens=None, num_ctx=None):
        self.requests.append({"model": model, "max_tokens": max_tokens})
        return Completion(text=self.text, model=model or "gemma4:12b", usage=Usage.of(5, 7))

    async def stream(self, messages, *, model=None, temperature=None, max_tokens=None, num_ctx=None):
        for symbol in self.text:
            yield StreamDelta(text=symbol)
        yield StreamDone(model=model or "gemma4:12b", usage=Usage.of(5, 7))

    async def list_models(self):
        return [ModelInfo(id="gemma4:12b", parameter_size="11.9B")]

    async def health(self):
        return not self.fail_health

    async def loaded_models(self):
        return []


def make_settings(**kw) -> Settings:
    base = dict(
        _env_file=None,
        api_keys="secret",
        default_model="gemma4:12b",
        num_ctx=8192,
        max_tokens_default=512,
        max_tokens_limit=2048,
        rate_limit_per_minute=60,
        rate_limit_burst=5,
        max_concurrency=1,
        max_queue=1,
        frontend_dir="__no_frontend__",
    )
    base.update(kw)
    return Settings(**base)


def make_app(*, settings=None, gateway=None, metrics=None, limiter=None, guard=None):
    settings = settings or make_settings()
    gateway = gateway or FakeGateway()
    metrics = metrics or Metrics()
    limiter = limiter or RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_burst)
    guard = guard or OverloadedGuard(settings.max_concurrency, settings.max_queue)
    service = ChatService(
        gateway,
        default_model=settings.default_model,
        num_ctx=settings.num_ctx,
        max_tokens_default=settings.max_tokens_default,
        max_tokens_limit=settings.max_tokens_limit,
    )
    app = create_app(settings, service, metrics, limiter, guard, gateway)
    deps = {
        "settings": settings,
        "gateway": gateway,
        "metrics": metrics,
        "limiter": limiter,
        "guard": guard,
        "service": service,
    }
    return app, deps
