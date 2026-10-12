from __future__ import annotations

import logging

import uvicorn

from app.application.chat_service import ChatService
from app.application.concurrency import OverloadedGuard
from app.application.rate_limit import RateLimiter
from app.config import Settings
from app.infrastructure.metrics import Metrics
from app.infrastructure.ollama_client import OllamaGateway
from app.presentation.app import create_app

logger = logging.getLogger("day30")


def build_app(settings: Settings | None = None):
    settings = settings or Settings()
    gateway = OllamaGateway(
        settings.ollama_base_url,
        keep_alive=settings.keep_alive,
        timeout=settings.request_timeout,
    )
    service = ChatService(
        gateway,
        default_model=settings.default_model,
        num_ctx=settings.num_ctx,
        max_tokens_default=settings.max_tokens_default,
        max_tokens_limit=settings.max_tokens_limit,
    )
    metrics = Metrics()
    limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_burst)
    guard = OverloadedGuard(settings.max_concurrency, settings.max_queue)
    return create_app(settings, service, metrics, limiter, guard, gateway)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings()
    if not settings.key_set():
        logger.warning(
            "API_KEYS не задан — сервис работает АНОНИМНО. Для сети задай API_KEYS."
        )
    logger.info("Слушаю %s:%s, модель %s, num_ctx %s", settings.host, settings.port, settings.default_model, settings.num_ctx)
    app = build_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
