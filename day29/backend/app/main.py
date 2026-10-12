from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.application.benchmark import BenchmarkRunner
from app.application.judge_deepseek import DeepSeekJudge
from app.application.optimization.ab_runner import ABRunner
from app.application.optimization.profiles import QUANT_ORDER, get_quant
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
log = logging.getLogger("day29")


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

    names: set[str] = set()
    try:
        names = {m.name for m in await ollama.list_models()}
    except Exception as e:  # noqa: BLE001
        log.warning("Не удалось получить список моделей: %s", e)
    for q in QUANT_ORDER:
        quant = get_quant(q)
        log.info("Квант %s: %s — %s", quant.name, quant.model, "есть" if quant.model in names else "нет")

    cloud = None
    if settings.deepseek_api_key:
        cloud = DeepSeekGateway(
            settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model
        )
        log.info("Облако: DeepSeek (%s) — судья и /eval", settings.deepseek_model)
    else:
        log.info("Облако: DEEPSEEK_API_KEY не задан — /ab будет без качества, /eval недоступен")

    judge = DeepSeekJudge(cloud) if cloud else None
    service = RagService(retriever, reranker, ollama, settings)
    store = JsonChatStore(Path(settings.data_dir) / "chats")
    benchmark = BenchmarkRunner(settings, service, ollama, cloud, judge) if cloud else None
    ab_runner = ABRunner(settings, service, ollama, judge)

    try:
        dim = int(getattr(embedder, "dim"))
        log.info("Эмбеддер: %s (dim=%d)", settings.embedder_model, dim)
    except Exception as e:  # noqa: BLE001
        log.warning("Не удалось проверить эмбеддер: %s", e)

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    router = build_router(
        service=service,
        ollama=ollama,
        cloud=cloud,
        benchmark=benchmark,
        ab_runner=ab_runner,
        store=store,
        settings=settings,
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
