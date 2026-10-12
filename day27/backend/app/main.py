from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.application.chat_service import ChatService
from app.config import Settings
from app.infrastructure.chat_store import JsonChatStore
from app.infrastructure.ollama_client import OllamaClient
from app.infrastructure.telegram_net import force_telegram_api_ip
from app.presentation.handlers import build_router
from app.presentation.middlewares import ErrorMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("day27")


async def run() -> None:
    settings = Settings()
    if not settings.telegram_bot_token or settings.telegram_bot_token.startswith("123456:"):
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN не задан. Скопируй .env.example в .env и вставь токен."
        )

    if settings.telegram_api_ip:
        force_telegram_api_ip(settings.telegram_api_ip)
        log.info("Telegram API IP override: api.telegram.org -> %s", settings.telegram_api_ip)

    llm = OllamaClient(
        base_url=settings.ollama_base_url,
        timeout=settings.request_timeout,
        keep_alive=settings.ollama_keep_alive,
        default_options=settings.ollama_options(),
    )
    store = JsonChatStore(Path(settings.data_dir) / "chats")
    service = ChatService(store, llm, settings)

    ok = await llm.health()
    log.info("Ollama: %s (%s)", "OK" if ok else "недоступна", settings.ollama_base_url)
    if ok:
        models = [m.name for m in await llm.list_models()]
        log.info("Модели: %s", ", ".join(models) or "—")
    log.info("Модель: %s", settings.ollama_model)

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    router = build_router(service, llm, settings)
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
        await llm.aclose()
        await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
