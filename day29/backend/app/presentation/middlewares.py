from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

import logging

log = logging.getLogger(__name__)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:  # noqa: BLE001
            log.exception("Handler failed")
            if isinstance(event, Message):
                try:
                    await event.answer("⚠️ Внутренняя ошибка. Попробуй ещё раз.")
                except Exception:  # noqa: BLE001
                    pass
            return None
