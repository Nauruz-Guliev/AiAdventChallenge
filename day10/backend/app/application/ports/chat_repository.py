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
        branch_id: str | None = None,
    ) -> Chat: ...

    async def save_facts(
        self, chat_id: str, branch_id: str | None, facts: dict[str, str]
    ) -> Chat: ...

    async def fork_branch(self, chat_id: str, after_index: int, name: str) -> Chat: ...

    async def set_active_branch(self, chat_id: str, branch_id: str) -> Chat: ...

    async def delete_branch(self, chat_id: str, branch_id: str) -> Chat: ...

