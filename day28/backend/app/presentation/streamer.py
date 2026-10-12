from __future__ import annotations

import time
from typing import Awaitable, Callable, Optional

from app.application.formatter import TELEGRAM_LIMIT, md_to_telegram_html, split_message


class TelegramMessageStreamer:
    """Стримит текст в сообщение Telegram через троттлинг-правки.

    `send(text) -> message` и `edit(message, text, parse_mode=None)` — внедряемые
    callable, поэтому класс тестируется без aiogram.
    """

    def __init__(
        self,
        send: Callable[[str], Awaitable[object]],
        edit: Callable[..., Awaitable[None]],
        min_interval: float = 1.2,
        limit: int = TELEGRAM_LIMIT,
    ) -> None:
        self._send = send
        self._edit = edit
        self._min_interval = min_interval
        self._limit = limit
        self._message: Optional[object] = None
        self._buffer = ""
        self._last_sent = ""
        self._last_time = 0.0
        self.overflowed = False

    async def start(self, placeholder: str = "💭 думает…") -> None:
        self._message = await self._send(placeholder)
        self._last_sent = placeholder
        self._last_time = time.monotonic()

    async def push(self, text: str, force: bool = False) -> None:
        self._buffer += text
        now = time.monotonic()
        if not force and (now - self._last_time) < self._min_interval:
            return
        await self._render()

    async def _render(self) -> None:
        if self._message is None:
            return
        while len(self._buffer) > self._limit:
            parts = split_message(self._buffer, self._limit)
            head = parts[0]
            rest = "".join(parts[1:])
            if head != self._last_sent:
                await self._safe_edit(head)
            self.overflowed = True
            self._buffer = rest
            self._message = await self._send("…")
            self._last_sent = "…"
        if self._buffer and self._buffer != self._last_sent:
            await self._safe_edit(self._buffer)

    async def _safe_edit(self, text: str, parse_mode: Optional[str] = None) -> None:
        try:
            await self._edit(self._message, text, parse_mode)
            self._last_sent = text
            self._last_time = time.monotonic()
        except Exception:
            pass

    async def finish(self, final_body: str, footer_text: str = "") -> None:
        if not self.overflowed:
            html = md_to_telegram_html(final_body)
            text = f"{html}\n{footer_text}" if footer_text else html
            if len(text) <= self._limit:
                try:
                    await self._edit(self._message, text, "HTML")
                    self._last_sent = text
                    return
                except Exception:
                    pass
            plain = f"{final_body}\n\n{footer_text}" if footer_text else final_body
            await self._emit_parts(plain)
            return
        # overflow: footer дописываем к хвосту последнего сообщения
        tail = self._buffer
        if not tail:
            if footer_text:
                await self._send(footer_text)
            return
        text = f"{tail}\n\n{footer_text}" if footer_text else tail
        await self._emit_parts(text)

    async def _emit_parts(self, text: str) -> None:
        parts = split_message(text, self._limit)
        await self._safe_edit(parts[0])
        for extra in parts[1:]:
            self._message = await self._send(extra)
            self._last_sent = extra
