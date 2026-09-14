import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import (
    Branch,
    BranchNotFound,
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatPersistenceError,
    ChatSummary,
    LastBranchError,
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
            branch = Branch(id=str(uuid.uuid4()), name="main")
            chat = Chat(
                id=str(uuid.uuid4()),
                title="Новый чат",
                created_at=now,
                updated_at=now,
                branches=[branch],
                active_branch_id=branch.id,
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

    async def append_exchange(
        self,
        chat_id: str,
        user_content: str,
        assistant_content: str,
        usage: TokenUsage,
        branch_id: str | None = None,
    ) -> Chat:
        return await self._mutate(
            chat_id,
            lambda chat: _do_append(chat, user_content, assistant_content, usage, branch_id),
        )

    async def save_facts(
        self, chat_id: str, branch_id: str | None, facts: dict[str, str]
    ) -> Chat:
        def mutate(chat: Chat) -> None:
            branch = _pick_branch(chat, branch_id)
            branch.facts = dict(facts)

        return await self._mutate(chat_id, mutate)

    async def fork_branch(self, chat_id: str, after_index: int, name: str) -> Chat:
        def mutate(chat: Chat) -> None:
            source = chat.active_branch
            if not 0 <= after_index <= len(source.messages):
                raise IndexError(after_index)
            branch = Branch(
                id=str(uuid.uuid4()),
                name=name,
                fork_at=after_index,
                messages=[
                    ChatMessage(
                        role=message.role,
                        content=message.content,
                        usage=message.usage,
                    )
                    for message in source.messages[:after_index]
                ],
                facts=dict(source.facts),
            )
            chat.branches.append(branch)
            chat.active_branch_id = branch.id

        return await self._mutate(chat_id, mutate)

    async def set_active_branch(self, chat_id: str, branch_id: str) -> Chat:
        def mutate(chat: Chat) -> None:
            _pick_branch(chat, branch_id)
            chat.active_branch_id = branch_id

        return await self._mutate(chat_id, mutate)

    async def delete_branch(self, chat_id: str, branch_id: str) -> Chat:
        def mutate(chat: Chat) -> None:
            if len(chat.branches) <= 1:
                raise LastBranchError(chat_id)
            branch = _pick_branch(chat, branch_id)
            chat.branches.remove(branch)
            if chat.active_branch_id == branch_id:
                chat.active_branch_id = chat.branches[0].id

        return await self._mutate(chat_id, mutate)

    async def _mutate(self, chat_id: str, mutate) -> Chat:
        async with self._lock:
            store = self._read_store()
            for index, stored_chat in enumerate(store["chats"]):
                if stored_chat["id"] == chat_id:
                    chat = _chat_from_dict(stored_chat)
                    mutate(chat)
                    updated = _chat_to_dict(chat)
                    updated["updated_at"] = _now()
                    store["chats"][index] = updated
                    self._write_store(store)
                    return chat
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


def _do_append(
    chat: Chat,
    user_content: str,
    assistant_content: str,
    usage: TokenUsage,
    branch_id: str | None,
) -> None:
    branch = _pick_branch(chat, branch_id)
    if (
        chat.title == "Новый чат"
        and branch is chat.active_branch
        and not branch.messages
    ):
        chat.title = _chat_title(user_content)
    branch.messages.extend(
        [
            ChatMessage(role="user", content=user_content),
            ChatMessage(role="assistant", content=assistant_content, usage=usage),
        ]
    )


def _pick_branch(chat: Chat, branch_id: str | None) -> Branch:
    if branch_id is None:
        return chat.active_branch
    for branch in chat.branches:
        if branch.id == branch_id:
            return branch
    raise BranchNotFound(branch_id)


def _chat_from_dict(stored_chat: dict) -> Chat:
    if "branches" in stored_chat:
        branches = [
            Branch(
                id=stored["id"],
                name=stored["name"],
                fork_at=stored.get("fork_at"),
                messages=[
                    _message_from_dict(message) for message in stored["messages"]
                ],
                facts=dict(stored.get("facts", {})),
            )
            for stored in stored_chat["branches"]
        ]
        return Chat(
            id=stored_chat["id"],
            title=stored_chat["title"],
            created_at=stored_chat["created_at"],
            updated_at=stored_chat["updated_at"],
            branches=branches,
            active_branch_id=stored_chat["active_branch_id"],
        )

    legacy_branch = Branch(
        id=str(uuid.uuid4()),
        name="main",
        messages=[
            _message_from_dict(message)
            for message in stored_chat.get("messages", [])
        ],
    )
    return Chat(
        id=stored_chat["id"],
        title=stored_chat["title"],
        created_at=stored_chat["created_at"],
        updated_at=stored_chat["updated_at"],
        branches=[legacy_branch],
        active_branch_id=legacy_branch.id,
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
        "active_branch_id": chat.active_branch_id,
        "branches": [
            {
                "id": branch.id,
                "name": branch.name,
                "fork_at": branch.fork_at,
                "facts": branch.facts,
                "messages": [
                    _message_to_dict(message) for message in branch.messages
                ],
            }
            for branch in chat.branches
        ],
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
