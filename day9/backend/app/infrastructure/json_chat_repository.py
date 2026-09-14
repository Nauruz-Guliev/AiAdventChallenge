import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import (
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatPersistenceError,
    ChatSummary,
    TokenUsage,
)


class JsonChatRepository:
    def __init__(self, path: Path):
        self._path = path
        self._lock = asyncio.Lock()

    async def create_chat(self) -> Chat:
        async with self._lock:
            store = self._read_store()
            now = _now()
            chat = Chat(
                id=str(uuid.uuid4()),
                title="Новый чат",
                created_at=now,
                updated_at=now,
                messages=[],
            )
            store["chats"].append(_chat_to_dict(chat))
            self._write_store(store)
            return chat

    async def list_chats(self) -> list[ChatSummary]:
        async with self._lock:
            store = self._read_store()
            return [
                ChatSummary(
                    id=chat["id"],
                    title=chat["title"],
                    created_at=chat["created_at"],
                    updated_at=chat["updated_at"],
                )
                for chat in store["chats"]
            ]

    async def get_chat(self, chat_id: str) -> Chat:
        async with self._lock:
            store = self._read_store()
            return _find_chat(store, chat_id)

    async def delete_chat(self, chat_id: str) -> None:
        async with self._lock:
            store = self._read_store()
            chats = store["chats"]
            remaining = [chat for chat in chats if chat["id"] != chat_id]
            if len(remaining) == len(chats):
                raise ChatNotFound(chat_id)
            store["chats"] = remaining
            self._write_store(store)

    async def save_summary(self, chat_id: str, summary: str, covers: int) -> Chat:
        async with self._lock:
            store = self._read_store()
            for stored_chat in store["chats"]:
                if stored_chat["id"] == chat_id:
                    stored_chat["summary"] = summary
                    stored_chat["summary_covers"] = covers
                    self._write_store(store)
                    return _chat_from_dict(stored_chat)
            raise ChatNotFound(chat_id)

    async def append_exchange(
        self,
        chat_id: str,
        user_content: str,
        assistant_content: str,
        usage: TokenUsage,
    ) -> Chat:
        async with self._lock:
            store = self._read_store()
            for stored_chat in store["chats"]:
                if stored_chat["id"] != chat_id:
                    continue

                if stored_chat["title"] == "Новый чат":
                    stored_chat["title"] = _chat_title(user_content)
                stored_chat["messages"].extend(
                    [
                        {"role": "user", "content": user_content},
                        {
                            "role": "assistant",
                            "content": assistant_content,
                            "usage": {
                                "prompt_tokens": usage.prompt_tokens,
                                "completion_tokens": usage.completion_tokens,
                                "total_tokens": usage.total_tokens,
                            },
                        },
                    ]
                )
                stored_chat["updated_at"] = _now()
                self._write_store(store)
                return _chat_from_dict(stored_chat)

            raise ChatNotFound(chat_id)

    def _read_store(self) -> dict:
        if not self._path.exists():
            store = {"version": 1, "chats": []}
            self._write_store(store)
            return store

        try:
            store = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ChatPersistenceError("Cannot read chat storage") from error

        if store.get("version") != 1 or not isinstance(store.get("chats"), list):
            raise ChatPersistenceError("Invalid chat storage format")
        return store

    def _write_store(self, store: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                delete=False,
            ) as temporary:
                json.dump(store, temporary, ensure_ascii=False, indent=2)
                temporary.write("\n")
                temp_path = temporary.name
            os.replace(temp_path, self._path)
        except OSError as error:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
            raise ChatPersistenceError("Cannot write chat storage") from error


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chat_title(content: str) -> str:
    compact = " ".join(content.split())
    if not compact:
        return "Новый чат"

    sentence_end = next(
        (
            index
            for index, character in enumerate(compact)
            if character in ".!?"
            and (index + 1 == len(compact) or compact[index + 1].isspace())
        ),
        None,
    )
    if sentence_end is not None and sentence_end + 1 >= 12:
        compact = compact[: sentence_end + 1]

    max_length = 40
    if len(compact) <= max_length:
        return compact

    words = []
    for word in compact.split():
        candidate = " ".join([*words, word])
        if len(candidate) >= max_length:
            break
        words.append(word)

    title = " ".join(words).rstrip(".,;:!?")
    return f"{title}…" or "Новый чат"


def _find_chat(store: dict, chat_id: str) -> Chat:
    for stored_chat in store["chats"]:
        if stored_chat["id"] == chat_id:
            return _chat_from_dict(stored_chat)
    raise ChatNotFound(chat_id)


def _chat_from_dict(stored_chat: dict) -> Chat:
    return Chat(
        id=stored_chat["id"],
        title=stored_chat["title"],
        created_at=stored_chat["created_at"],
        updated_at=stored_chat["updated_at"],
        messages=[_message_from_dict(message) for message in stored_chat["messages"]],
        summary=stored_chat.get("summary"),
        summary_covers=stored_chat.get("summary_covers", 0),
    )


def _message_from_dict(message: dict) -> ChatMessage:
    usage = message.get("usage")
    return ChatMessage(
        role=message["role"],
        content=message["content"],
        usage=TokenUsage(**usage) if usage else None,
    )


def _chat_to_dict(chat: Chat) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
        "messages": [_message_to_dict(message) for message in chat.messages],
        "summary": chat.summary,
        "summary_covers": chat.summary_covers,
    }


def _message_to_dict(message: ChatMessage) -> dict:
    stored = {"role": message.role, "content": message.content}
    if message.usage is not None:
        stored["usage"] = {
            "prompt_tokens": message.usage.prompt_tokens,
            "completion_tokens": message.usage.completion_tokens,
            "total_tokens": message.usage.total_tokens,
        }
    return stored
