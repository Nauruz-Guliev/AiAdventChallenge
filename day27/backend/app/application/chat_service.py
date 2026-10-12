from __future__ import annotations

from typing import AsyncIterator, Optional

from app.application.formatter import footer
from app.config import Settings
from app.domain.models import ChatMessage, ChatState, GenerationStats, Role
from app.infrastructure.chat_store import JsonChatStore
from app.ports.llm import LLMClient, StreamDelta, StreamDone


class ChatService:
    def __init__(self, store: JsonChatStore, llm: LLMClient, settings: Settings) -> None:
        self._store = store
        self._llm = llm
        self._settings = settings
        self._last_stats: dict[int, GenerationStats] = {}

    def get_state(self, chat_id: int) -> ChatState:
        st = self._store.load(chat_id)
        if st is None:
            st = ChatState(
                chat_id=chat_id,
                system_prompt=self._settings.system_prompt,
                model=self._settings.ollama_model,
            )
        if not st.model:
            st.model = self._settings.ollama_model
        return st

    def trim(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        kept = (
            messages[-self._settings.history_max_messages :]
            if self._settings.history_max_messages > 0
            else list(messages)
        )
        while kept and sum(len(m.content) for m in kept) > self._settings.history_max_chars:
            kept = kept[1:]
        return kept

    def _build_payload(
        self, state: ChatState, user_message: ChatMessage
    ) -> list[ChatMessage]:
        history = self.trim(state.history())
        system = ChatMessage(Role.SYSTEM, state.system_prompt)
        return [system, *history, user_message]

    async def stream(
        self,
        state: ChatState,
        user_message: ChatMessage,
        images: Optional[list[str]] = None,
    ) -> AsyncIterator[StreamDelta | StreamDone]:
        if images:
            user_message.images = images
        payload = self._build_payload(state, user_message)

        assistant_text = ""
        stats: GenerationStats | None = None
        async for event in self._llm.stream_chat(
            payload, state.model, options=self._settings.ollama_options()
        ):
            if isinstance(event, StreamDelta) and event.kind == "content":
                assistant_text += event.text
            elif isinstance(event, StreamDone):
                stats = event.stats
            yield event

        if stats is not None:
            self._last_stats[state.chat_id] = stats

        stored_user = ChatMessage(
            role=Role.USER,
            content="[фото]" if images else user_message.content,
        )
        state.messages.append(stored_user)
        state.messages.append(ChatMessage(role=Role.ASSISTANT, content=assistant_text))
        state.messages = self.trim(state.messages)
        self._store.save(state)

    def reset(self, chat_id: int) -> ChatState:
        st = self.get_state(chat_id)
        st.messages = []
        self._store.save(st)
        return st

    async def set_model(self, state: ChatState, name: str) -> bool:
        models = await self._llm.list_models()
        if any(m.name == name for m in models):
            state.model = name
            self._store.save(state)
            return True
        return False

    def set_thinking(self, state: ChatState, on: bool) -> None:
        state.show_thinking = on
        self._store.save(state)

    def stats(self, state: ChatState) -> str:
        s = self._last_stats.get(state.chat_id)
        speed = f"{s.tokens_per_second:.0f} tok/s" if s and s.tokens_per_second > 0 else "—"
        return (
            f"Модель: {state.model}\n"
            f"Скорость последнего ответа: {speed}\n"
            f"Сообщений в истории: {len(state.history())}\n"
            f"Показывать размышления: {'да' if state.show_thinking else 'нет'}"
        )

    def footer_for(self, state: ChatState) -> str:
        return footer(self._last_stats.get(state.chat_id), state.model)
