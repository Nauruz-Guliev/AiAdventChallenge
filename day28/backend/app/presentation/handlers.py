from __future__ import annotations

import asyncio
import time

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from app.application.formatter import footer, split_message
from app.config import Settings
from app.domain.models import ChatMessage, ChatState, CloudUnavailable, Role
from app.ports.llm import OllamaUnavailable, StreamDelta, StreamDone
from app.presentation import messages
from app.presentation.keyboards import answer_keyboard
from app.presentation.streamer import TelegramMessageStreamer


def build_router(service, ollama, cloud, benchmark, store, settings: Settings) -> Router:
    router = Router()
    locks: dict[int, asyncio.Lock] = {}
    eval_locks: dict[int, asyncio.Lock] = {}

    def lock_for(chat_id: int) -> asyncio.Lock:
        return locks.setdefault(chat_id, asyncio.Lock())

    def eval_lock_for(chat_id: int) -> asyncio.Lock:
        return eval_locks.setdefault(chat_id, asyncio.Lock())

    def get_state(chat_id: int) -> ChatState:
        st = store.load(chat_id)
        if st is None:
            st = ChatState(
                chat_id=chat_id,
                system_prompt="",
                model=settings.ollama_model,
                think=settings.think_default,
            )
        if not st.model:
            st.model = settings.ollama_model
        return st

    def save(state: ChatState) -> None:
        store.save(state)

    def remember(state: ChatState, question: str, reply_text: str) -> None:
        state.messages.append(ChatMessage(Role.USER, question))
        state.messages.append(ChatMessage(Role.ASSISTANT, reply_text))
        if settings.history_max_messages > 0:
            state.messages = state.messages[-settings.history_max_messages :]
        state.last_question = question
        save(state)

    @router.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        await message.answer(
            messages.START_TEXT.format(model=settings.ollama_model), parse_mode="HTML"
        )

    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(messages.HELP_TEXT, parse_mode="HTML")

    @router.message(Command("id"))
    async def cmd_id(message: Message) -> None:
        await message.answer(f"chat_id = <code>{message.chat.id}</code>", parse_mode="HTML")

    @router.message(Command("new", "reset"))
    async def cmd_reset(message: Message) -> None:
        st = get_state(message.chat.id)
        st.messages = []
        st.last_question = ""
        save(st)
        await message.answer("🧹 История очищена.")

    @router.message(Command("rag"))
    async def cmd_rag(message: Message) -> None:
        st = get_state(message.chat.id)
        st.rag_enabled = True
        save(st)
        await message.answer("🔎 Поиск по базе включён.")

    @router.message(Command("norag"))
    async def cmd_norag(message: Message) -> None:
        st = get_state(message.chat.id)
        st.rag_enabled = False
        save(st)
        await message.answer("🧠 Отвечаю без поиска (только знания модели).")

    @router.message(Command("think"))
    async def cmd_think(message: Message, command: CommandObject) -> None:
        arg = (command.args or "").strip().lower()
        if arg not in {"on", "off"}:
            await message.answer("Использование: /think on|off")
            return
        st = get_state(message.chat.id)
        st.think = arg == "on"
        save(st)
        await message.answer(f"Показ «размышлений»: {'вкл' if st.think else 'выкл'}")

    @router.message(Command("status"))
    async def cmd_status(message: Message) -> None:
        st = get_state(message.chat.id)
        ok = await ollama.health() if ollama is not None else False
        await message.answer(
            "📟 Состояние\n"
            f"Локальная модель: <b>{st.model}</b> · Ollama: {'OK' if ok else 'нет'}\n"
            f"Индекс: <code>{settings.index_path}</code>\n"
            f"Эмбеддер: <code>{settings.embedder_model}</code>\n"
            f"Режим: {'RAG (поиск по базе)' if st.rag_enabled else 'без RAG'}\n"
            f"Облако: {'доступно' if cloud else 'нет ключа'}",
            parse_mode="HTML",
        )

    async def run_stream(message: Message, question: str) -> None:
        st = get_state(message.chat.id)
        lock = lock_for(message.chat.id)
        if lock.locked():
            await message.answer(messages.BUSY_TEXT)
            return
        async with lock:
            prepared = service.prepare(question, use_rag=st.rag_enabled)
            if not prepared.answerable:
                from app.application.prompt import NO_ANSWER_TEXT

                st.last_question = question
                save(st)
                await message.answer(
                    NO_ANSWER_TEXT, reply_markup=answer_keyboard(st.rag_enabled)
                )
                return
            streamer = TelegramMessageStreamer(
                send=lambda t, pm=None: message.answer(t, parse_mode=pm),
                edit=lambda m, t, pm=None: m.edit_text(t, parse_mode=pm),
                min_interval=1.2,
            )
            await streamer.start()
            full, stats = "", None
            try:
                async for event in ollama.stream_chat(
                    prepared.messages, think=st.think, options=settings.ollama_options()
                ):
                    if isinstance(event, StreamDelta) and event.kind == "content":
                        full += event.text
                        await streamer.push(event.text)
                    elif isinstance(event, StreamDone):
                        stats = event.stats
            except OllamaUnavailable:
                await message.answer(messages.OFFLINE_TEXT)
                return
            answer = service.finalize(full, prepared, stats)
            await streamer.finish(full, footer(stats, st.model))
            await message.answer(
                messages.sources_text(answer), reply_markup=answer_keyboard(st.rag_enabled)
            )
            remember(st, question, answer.reply)

    async def cmd_compare_like(message: Message, question: str) -> None:
        if cloud is None:
            await message.answer(messages.NO_CLOUD_TEXT)
            return
        st = get_state(message.chat.id)
        prepared = service.prepare(question, use_rag=st.rag_enabled)
        await message.answer("⚖️ Считаю оба ответа…")
        t0 = time.perf_counter()
        local = await service.answer(question, st.history(), use_rag=st.rag_enabled)
        local_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        try:
            cloud_completion = await cloud.complete(prepared.messages)
        except CloudUnavailable:
            await message.answer(messages.NO_CLOUD_TEXT)
            return
        cloud_ms = (time.perf_counter() - t1) * 1000
        await message.answer(
            f"🖥️ <b>Локально</b> ({local_ms:.0f} мс)\n{local.reply}", parse_mode="HTML"
        )
        await message.answer(
            f"☁️ <b>Облако</b> ({cloud_ms:.0f} мс)\n{cloud_completion.text}", parse_mode="HTML"
        )
        remember(st, question, local.reply)

    async def cmd_eval_like(message: Message, runs: int) -> None:
        if benchmark is None:
            await message.answer(messages.NO_CLOUD_TEXT)
            return
        if eval_lock_for(message.chat.id).locked():
            await message.answer(messages.EVAL_BUSY_TEXT)
            return
        progress_msg = await message.answer(messages.EVAL_STARTED_TEXT.format(runs=runs))
        lock = eval_lock_for(message.chat.id)

        async def worker() -> None:
            async with lock:
                async def on_progress(done: int, total: int) -> None:
                    try:
                        await progress_msg.edit_text(f"🧪 Прогон: {done}/{total}…")
                    except Exception:  # noqa: BLE001
                        pass

                try:
                    report = await benchmark.run(runs=runs, on_progress=on_progress)
                except Exception as e:  # noqa: BLE001
                    await message.answer(f"⚠️ Прогон не удался: {e}")
                    return
            for part in split_message(messages.eval_report_text(report)):
                await message.answer(part)

        asyncio.create_task(worker())

    @router.message(Command("compare"))
    async def cmd_compare(message: Message, command: CommandObject) -> None:
        question = (command.args or "").strip()
        if not question:
            await message.answer("Использование: /compare &lt;вопрос&gt;", parse_mode="HTML")
            return
        await cmd_compare_like(message, question)

    @router.message(Command("eval"))
    async def cmd_eval(message: Message, command: CommandObject) -> None:
        runs = settings.eval_runs
        arg = (command.args or "").strip()
        if arg.isdigit() and int(arg) > 0:
            runs = int(arg)
        await cmd_eval_like(message, runs)

    @router.callback_query(F.data == "toggle_rag")
    async def cb_toggle_rag(query: CallbackQuery) -> None:
        st = get_state(query.message.chat.id)
        st.rag_enabled = not st.rag_enabled
        save(st)
        await query.answer("RAG включён" if st.rag_enabled else "RAG выключен")
        try:
            await query.message.edit_reply_markup(reply_markup=answer_keyboard(st.rag_enabled))
        except Exception:  # noqa: BLE001
            pass

    @router.callback_query(F.data == "cloud")
    async def cb_cloud(query: CallbackQuery) -> None:
        st = get_state(query.message.chat.id)
        if cloud is None:
            await query.answer("Облако недоступно", show_alert=True)
            return
        if not st.last_question:
            await query.answer("Сначала задай вопрос", show_alert=True)
            return
        await query.answer()
        prepared = service.prepare(st.last_question, use_rag=st.rag_enabled)
        try:
            completion = await cloud.complete(prepared.messages)
        except CloudUnavailable:
            await query.message.answer(messages.NO_CLOUD_TEXT)
            return
        await query.message.answer(
            f"☁️ <b>Облако</b>\n{completion.text}", parse_mode="HTML"
        )

    @router.callback_query(F.data == "compare")
    async def cb_compare(query: CallbackQuery) -> None:
        st = get_state(query.message.chat.id)
        if not st.last_question:
            await query.answer("Сначала задай вопрос", show_alert=True)
            return
        await query.answer()
        await cmd_compare_like(query.message, st.last_question)

    @router.callback_query(F.data == "eval")
    async def cb_eval(query: CallbackQuery) -> None:
        await query.answer()
        await cmd_eval_like(query.message, settings.eval_runs)

    @router.message(F.text)
    async def on_text(message: Message) -> None:
        await run_stream(message, message.text or "")

    return router
