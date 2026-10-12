from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.domain.models import Overloaded


class OverloadedGuard:
    """Ограничивает одновременные запросы и не даёт очереди расти бесконечно."""

    def __init__(self, max_concurrency: int, max_queue: int) -> None:
        self._limit = max(1, max_concurrency)
        self._max_queue = max(0, max_queue)
        self._active = 0
        self._waiting = 0
        self._cond = asyncio.Condition()

    @property
    def active(self) -> int:
        return self._active

    @property
    def waiting(self) -> int:
        return self._waiting

    async def _enter(self) -> None:
        async with self._cond:
            if self._active >= self._limit:
                if self._waiting >= self._max_queue:
                    raise Overloaded("Сервис перегружен, попробуйте позже", retry_after=2)
                self._waiting += 1
                try:
                    await self._cond.wait_for(lambda: self._active < self._limit)
                finally:
                    self._waiting -= 1
            self._active += 1

    async def _exit(self) -> None:
        async with self._cond:
            self._active -= 1
            self._cond.notify_all()

    async def acquire(self) -> None:
        await self._enter()

    async def release(self) -> None:
        await self._exit()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        await self._enter()
        try:
            yield
        finally:
            await self._exit()
