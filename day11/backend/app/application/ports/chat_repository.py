from typing import Protocol

from app.domain.models import (
    Chat,
    ChatSummary,
    LongTermEntry,
    LongTermMemory,
    MemoryCandidate,
    TokenUsage,
    WorkingMemory,
)


class ChatRepository(Protocol):
    async def create_chat(self, title: str = "Новый чат") -> Chat: ...

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

    async def clear_messages(self, chat_id: str) -> Chat: ...

    async def get_working_memory(self, chat_id: str) -> WorkingMemory: ...

    async def save_working_memory(
        self, chat_id: str, working: WorkingMemory
    ) -> Chat: ...

    async def complete_working_memory(self, chat_id: str) -> Chat: ...

    async def reset_working_memory(self, chat_id: str) -> Chat: ...

    async def get_long_term(self) -> LongTermMemory: ...

    async def replace_long_term(self, long_term: LongTermMemory) -> LongTermMemory: ...

    async def add_long_term_entry(
        self, category: str, text: str, source_chat_id: str
    ) -> LongTermEntry: ...

    async def delete_long_term_entry(self, category: str, entry_id: str) -> None: ...

    async def add_candidates(
        self, items: list[dict], source_chat_id: str
    ) -> list[MemoryCandidate]: ...

    async def list_candidates(
        self, status: str | None = "pending"
    ) -> list[MemoryCandidate]: ...

    async def approve_candidate(
        self,
        candidate_id: str,
        category: str | None = None,
        text: str | None = None,
    ) -> LongTermEntry: ...

    async def reject_candidate(self, candidate_id: str) -> MemoryCandidate: ...

    async def clear_rejected_candidates(self) -> int: ...