from __future__ import annotations

import asyncio
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from app.application.chat_service import ChatService
from app.application.vision import encode_photo, photo_prompt
from app.config import Settings
from app.domain.models import ChatMessage, Role
from app.presentation import messages
from app.presentation.streamer import TelegramMessageStreamer
from app.ports.llm import OllamaUnavailable, StreamDelta


def build_router(service: ChatService, llm, settings: Settings) -> Router:
    router = Router()
    locks: dict[int, asyncio.Lock] = {}

    def lock_for(chat_id: int) -> asyncio.Lock:
        lock = locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            locks[chat_id] = lock
        return lock

    @router.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        await message.answer(
            messages.START_TEXT.format(
                model=settings.ollama_model, base_url=settings.ollama_base_url
            ),
            parse_mode="HTML",
        )

    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(messages.HELP_TEXT, parse_mode="HTML")

    @router.message(Command("id"))
    async def cmd_id(message: Message) -> None:
        await message.answer(f"chat_id = <code>{message.chat.id}</code>", parse_mode="HTML")

    @router.message(Command("new", "reset"))
    async def cmd_reset(message: Message) -> None:
        service.reset(message.chat.id)
        await message.answer("🧹 История очищена.")

    @router.message(Command("model"))
    async def cmd_model(message: Message, command: CommandObject) -> None:
        state = service.get_state(message.chat.id)
        name = (command.args or "").strip()
        if not name:
            models = await llm.list_models()
            listing = ", ".join(f"<code>{m.name}</code>" for m in models) or "—"
            await message.answer(
                f"Текущая модель: <b>{state.model}</b>\nДоступные: {listing}",
                parse_mode="HTML",
            )
            return
        ok = await service.set_model(state, name)
        await message.answer(
            f"Модель переключена на <b>{name}</b>."
            if ok
            else f"Модель <code>{name}</code> не найдена.",
            parse_mode="HTML",
        )

    @router.message(Command("stats"))
    async def cmd_stats(message: Message) -> None:
        await message.answer(service.stats(service.get_state(message.chat.id)))

    @router.message(Command("think"))
    async def cmd_think(message: Message, command: CommandObject) -> None:
        arg = (command.args or "").strip().lower()
        if arg not in {"on", "off"}:
            await message.answer("Использование: /think on|off")
            return
        state = service.get_state(message.chat.id)
        service.set_thinking(state, arg == "on")
        await message.answer(f"Показ размышлений: {'вкл' if arg == 'on' else 'выкл'}")

    async def run_generation(message: Message, user_msg: ChatMessage, images=None) -> None:
        state = service.get_state(message.chat.id)
        lock = lock_for(message.chat.id)
        if lock.locked():
            await message.answer(messages.BUSY_TEXT)
            return
        async with lock:
            streamer = TelegramMessageStreamer(
                send=lambda t: message.answer(t),
                edit=lambda m, t, pm=None: m.edit_text(t, parse_mode=pm),
                min_interval=1.2,
            )
            await streamer.start()
            full = ""
            thinking = ""
            try:
                async for event in service.stream(state, user_msg, images=images):
                    if isinstance(event, StreamDelta):
                        if event.kind == "thinking":
                            thinking += event.text
                        else:
                            full += event.text
                            await streamer.push(event.text)
            except OllamaUnavailable:
                await message.answer(messages.OFFLINE_TEXT)
                return
            await streamer.finish(full, service.footer_for(state))
            if state.show_thinking and thinking.strip():
                await message.answer("💭 Размышления:\n" + thinking.strip())

    @router.message(F.photo)
    async def on_photo(message: Message) -> None:
        photo = message.photo[-1]
        tg_file = await message.bot.get_file(photo.file_id)
        buf = BytesIO()
        await message.bot.download_file(tg_file.file_path, buf)
        b64 = encode_photo(buf.getvalue())
        user_msg = ChatMessage(Role.USER, photo_prompt(message.caption), images=[b64])
        await run_generation(message, user_msg, images=[b64])

    @router.message(F.text)
    async def on_text(message: Message) -> None:
        await run_generation(message, ChatMessage(Role.USER, message.text or ""))

    return router
