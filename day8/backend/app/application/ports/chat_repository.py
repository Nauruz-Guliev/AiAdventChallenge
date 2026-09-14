from typing import Protocol

from app.domain.models import Chat, ChatSummary, TokenUsage


class ChatRepository(Protocol):
    async def create_chat(self) -> Chat: ...

    async def list_chats(self) -> list[ChatSummary]: ...

    async def get_chat(self, chat_id: str) -> Chat: ...

    async def delete_chat(self, chat_id: str) -> None: ...

    async def append_exchange(
        self,
        chat_id: str,
        user_content: str,
        assistant_content: str,
        usage: TokenUsage,
    ) -> Chat: ...
