from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.application.benchmark import BenchmarkRunner
from app.application.judge_deepseek import DeepSeekJudge
from app.application.rag_service import RagService
from app.config import Settings
from app.infrastructure.chat_store import JsonChatStore
from app.infrastructure.deepseek_gateway import DeepSeekGateway
from app.infrastructure.embeddings import get_embedder
from app.infrastructure.heuristic_reranker import HeuristicReranker
from app.infrastructure.ollama_client import OllamaClient
from app.infrastructure.retrieval import JsonRetriever
from app.infrastructure.telegram_net import force_telegram_api_ip
from app.presentation.handlers import build_router
from app.presentation.middlewares import ErrorMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("day28")


async def run() -> None:
    settings = Settings()
    if not settings.telegram_bot_token or settings.telegram_bot_token.startswith("123456:"):
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN не задан. Скопируй .env.example в .env и вставь токен."
        )

    if settings.telegram_api_ip:
        force_telegram_api_ip(settings.telegram_api_ip)
        log.info("Telegram API IP override: api.telegram.org -> %s", settings.telegram_api_ip)

    embedder = get_embedder(settings.embedder, settings.embedder_model)
    retriever = JsonRetriever(settings.index_path, embedder, top_k=settings.top_k_pre)
    reranker = HeuristicReranker()
    log.info("Индекс: %s (%d чанков)", settings.index_path, retriever.chunk_count())

    ollama = OllamaClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout=settings.request_timeout,
        keep_alive=settings.ollama_keep_alive,
        default_options=settings.ollama_options(),
    )
    ok = await ollama.health()
    log.info("Ollama: %s (%s)", "OK" if ok else "недоступна", settings.ollama_base_url)
    log.info("Модель: %s", settings.ollama_model)

    cloud = None
    if settings.deepseek_api_key:
        cloud = DeepSeekGateway(
            settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model
        )
        log.info("Облако: DeepSeek (%s) — доступно для сравнения", settings.deepseek_model)
    else:
        log.info("Облако: DEEPSEEK_API_KEY не задан — сравнение недоступно")

    judge = DeepSeekJudge(cloud) if cloud else None
    service = RagService(retriever, reranker, ollama, settings)
    store = JsonChatStore(Path(settings.data_dir) / "chats")
    benchmark = BenchmarkRunner(settings, service, ollama, cloud, judge) if cloud else None

    try:
        dim = int(getattr(embedder, "dim"))
        log.info("Эмбеддер: %s (dim=%d)", settings.embedder_model, dim)
    except Exception as e:  # noqa: BLE001
        log.warning("Не удалось проверить эмбеддер: %s", e)

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    router = build_router(
        service=service, ollama=ollama, cloud=cloud, benchmark=benchmark,
        store=store, settings=settings,
    )
    router.message.middleware.register(ErrorMiddleware())
    dp.include_router(router)

    try:
        log.info("Bot started. Polling…")
        while True:
            try:
                await dp.start_polling(bot)
                break
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("Polling interrupted: %s. Reconnecting in 3s…", e)
                await asyncio.sleep(3)
    finally:
        await ollama.aclose()
        await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
