import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import (
    LONG_TERM_CATEGORIES,
    CandidateConflict,
    CandidateNotFound,
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatPersistenceError,
    ChatSummary,
    LongTermEntry,
    LongTermEntryNotFound,
    LongTermMemory,
    MemoryCandidate,
    TokenUsage,
    WorkingMemory,
)


class JsonMemoryRepository:
    def __init__(
        self, chats_dir: Path, long_term_path: Path, candidates_path: Path
    ):
        self._chats_dir = chats_dir
        self._long_term_path = long_term_path
        self._candidates_path = candidates_path
        self._lock = asyncio.Lock()

    async def create_chat(self, title: str = "Новый чат") -> Chat:
        async with self._lock:
            now = _now()
            chat = Chat(
                id=str(uuid.uuid4()), title=title, created_at=now, updated_at=now
            )
            self._save_chat(chat)
            return chat

    async def list_chats(self) -> list[ChatSummary]:
        async with self._lock:
            summaries = []
            for path in sorted(self._chats_dir.glob("*.json")):
                chat = _chat_from_dict(self._read_json(path))
                summaries.append(
                    ChatSummary(
                        id=chat.id,
                        title=chat.title,
                        created_at=chat.created_at,
                        updated_at=chat.updated_at,
                    )
                )
            return summaries

    async def get_chat(self, chat_id: str) -> Chat:
        async with self._lock:
            return self._read_chat(chat_id)

    async def delete_chat(self, chat_id: str) -> None:
        async with self._lock:
            path = self._chat_path(chat_id)
            if not path.exists():
                raise ChatNotFound(chat_id)
            path.unlink()

    async def append_exchange(
        self,
        chat_id: str,
        user_content: str,
        assistant_content: str,
        usage: TokenUsage,
    ) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            if chat.title == "Новый чат" and not chat.messages:
                chat.title = _chat_title(user_content)
            chat.messages.extend(
                [
                    ChatMessage(role="user", content=user_content),
                    ChatMessage(
                        role="assistant", content=assistant_content, usage=usage
                    ),
                ]
            )
            return self._save_chat(chat)

    async def clear_messages(self, chat_id: str) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            chat.messages = []
            return self._save_chat(chat)

    async def get_working_memory(self, chat_id: str) -> WorkingMemory:
        async with self._lock:
            return self._read_chat(chat_id).working_memory

    async def save_working_memory(
        self, chat_id: str, working: WorkingMemory
    ) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            chat.working_memory = working
            return self._save_chat(chat)

    async def complete_working_memory(self, chat_id: str) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            chat.working_memory.status = "done"
            return self._save_chat(chat)

    async def reset_working_memory(self, chat_id: str) -> Chat:
        async with self._lock:
            chat = self._read_chat(chat_id)
            chat.working_memory = WorkingMemory()
            return self._save_chat(chat)

    async def get_long_term(self) -> LongTermMemory:
        async with self._lock:
            return self._read_long_term()

    async def replace_long_term(self, long_term: LongTermMemory) -> LongTermMemory:
        async with self._lock:
            self._write_long_term(long_term)
            return long_term

    async def add_long_term_entry(
        self, category: str, text: str, source_chat_id: str
    ) -> LongTermEntry:
        async with self._lock:
            long_term = self._read_long_term()
            entries = long_term.entries(category)
            if any(item.text == text for item in entries):
                raise CandidateConflict(text)
            entry = LongTermEntry(
                id=str(uuid.uuid4()),
                text=text,
                source_chat_id=source_chat_id,
                created_at=_now(),
            )
            entries.append(entry)
            self._write_long_term(long_term)
            return entry

    async def delete_long_term_entry(self, category: str, entry_id: str) -> None:
        async with self._lock:
            long_term = self._read_long_term()
            entries = long_term.entries(category)
            remaining = [item for item in entries if item.id != entry_id]
            if len(remaining) == len(entries):
                raise LongTermEntryNotFound(entry_id)
            setattr(long_term, category, remaining)
            self._write_long_term(long_term)

    async def add_candidates(
        self, items: list[dict], source_chat_id: str
    ) -> list[MemoryCandidate]:
        async with self._lock:
            store = self._read_candidates()
            pending_texts = {
                item["text"]
                for item in store["candidates"]
                if item["status"] == "pending"
            }
            created = []
            for item in items:
                if item["text"] in pending_texts:
                    continue
                candidate = MemoryCandidate(
                    id=str(uuid.uuid4()),
                    text=item["text"],
                    category=item["category"],
                    source_chat_id=source_chat_id,
                    created_at=_now(),
                )
                store["candidates"].append(_candidate_to_dict(candidate))
                pending_texts.add(item["text"])
                created.append(candidate)
            self._write_candidates(store)
            return created

    async def list_candidates(
        self, status: str | None = "pending"
    ) -> list[MemoryCandidate]:
        async with self._lock:
            store = self._read_candidates()
            return [
                _candidate_from_dict(item)
                for item in store["candidates"]
                if status is None or item["status"] == status
            ]

    async def approve_candidate(
        self,
        candidate_id: str,
        category: str | None = None,
        text: str | None = None,
    ) -> LongTermEntry:
        async with self._lock:
            store = self._read_candidates()
            candidate = _find_candidate(store, candidate_id)
            if candidate.status != "pending":
                raise CandidateConflict(candidate_id)
            target_category = category or candidate.category
            if target_category not in LONG_TERM_CATEGORIES:
                raise ValueError(f"unknown category: {target_category}")
            final_text = (candidate.text if text is None else text).strip()
            if not final_text:
                raise ValueError("empty entry text")
            long_term = self._read_long_term()
            entries = long_term.entries(target_category)
            if any(item.text == final_text for item in entries):
                raise CandidateConflict(final_text)
            entry = LongTermEntry(
                id=str(uuid.uuid4()),
                text=final_text,
                source_chat_id=candidate.source_chat_id,
                created_at=_now(),
            )
            entries.append(entry)
            self._write_long_term(long_term)
            _set_candidate_status(store, candidate_id, "approved")
            self._write_candidates(store)
            return entry

    async def reject_candidate(self, candidate_id: str) -> MemoryCandidate:
        async with self._lock:
            store = self._read_candidates()
            candidate = _find_candidate(store, candidate_id)
            if candidate.status != "pending":
                raise CandidateConflict(candidate_id)
            _set_candidate_status(store, candidate_id, "rejected")
            self._write_candidates(store)
            return candidate

    async def clear_rejected_candidates(self) -> int:
        async with self._lock:
            store = self._read_candidates()
            kept = [
                item for item in store["candidates"] if item["status"] != "rejected"
            ]
            removed = len(store["candidates"]) - len(kept)
            store["candidates"] = kept
            self._write_candidates(store)
            return removed

    def _chat_path(self, chat_id: str) -> Path:
        return self._chats_dir / f"{chat_id}.json"

    def _read_chat(self, chat_id: str) -> Chat:
        path = self._chat_path(chat_id)
        if not path.exists():
            raise ChatNotFound(chat_id)
        return _chat_from_dict(self._read_json(path))

    def _save_chat(self, chat: Chat) -> Chat:
        chat.updated_at = _now()
        self._write_json(self._chat_path(chat.id), _chat_to_dict(chat))
        return chat

    def _read_long_term(self) -> LongTermMemory:
        if not self._long_term_path.exists():
            return LongTermMemory()
        payload = self._read_json(self._long_term_path)
        return LongTermMemory(
            profile=[_entry_from_dict(item) for item in payload.get("profile", [])],
            decisions=[_entry_from_dict(item) for item in payload.get("decisions", [])],
            knowledge=[_entry_from_dict(item) for item in payload.get("knowledge", [])],
        )

    def _write_long_term(self, long_term: LongTermMemory) -> None:
        self._write_json(
            self._long_term_path,
            {
                "version": 1,
                "profile": [_entry_to_dict(item) for item in long_term.profile],
                "decisions": [_entry_to_dict(item) for item in long_term.decisions],
                "knowledge": [_entry_to_dict(item) for item in long_term.knowledge],
            },
        )

    def _read_candidates(self) -> dict:
        if not self._candidates_path.exists():
            return {"version": 1, "candidates": []}
        return self._read_json(self._candidates_path)

    def _write_candidates(self, store: dict) -> None:
        self._write_json(self._candidates_path, store)

    def _read_json(self, path: Path) -> dict:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ChatPersistenceError(f"Cannot read {path.name}") from error
        if not isinstance(payload, dict):
            raise ChatPersistenceError(f"Invalid format in {path.name}")
        return payload

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
            ) as temporary:
                json.dump(payload, temporary, ensure_ascii=False, indent=2)
                temporary.write("\n")
                temp_path = temporary.name
            os.replace(temp_path, path)
        except OSError as error:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
            raise ChatPersistenceError(f"Cannot write {path.name}") from error


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chat_title(content: str) -> str:
    compact = " ".join(content.split())
    if not compact:
        return "Новый чат"
    max_length = 40
    if len(compact) <= max_length:
        return compact
    words: list[str] = []
    for word in compact.split():
        candidate = " ".join([*words, word])
        if len(candidate) >= max_length:
            break
        words.append(word)
    title = " ".join(words).rstrip(".,;:!?")
    return f"{title}…" or "Новый чат"


def _find_candidate(store: dict, candidate_id: str) -> MemoryCandidate:
    for item in store["candidates"]:
        if item["id"] == candidate_id:
            return _candidate_from_dict(item)
    raise CandidateNotFound(candidate_id)


def _set_candidate_status(store: dict, candidate_id: str, status: str) -> None:
    for item in store["candidates"]:
        if item["id"] == candidate_id:
            item["status"] = status
            return


def _working_to_dict(working: WorkingMemory) -> dict:
    return {
        "goal": working.goal,
        "constraints": list(working.constraints),
        "decisions": list(working.decisions),
        "status": working.status,
    }


def _working_from_dict(payload: dict | None) -> WorkingMemory:
    payload = payload or {}
    return WorkingMemory(
        goal=payload.get("goal", ""),
        constraints=list(payload.get("constraints", [])),
        decisions=list(payload.get("decisions", [])),
        status=payload.get("status", "active"),
    )


def _message_to_dict(message: ChatMessage) -> dict:
    stored = {"role": message.role, "content": message.content}
    if message.usage is not None:
        stored["usage"] = {
            "prompt_tokens": message.usage.prompt_tokens,
            "completion_tokens": message.usage.completion_tokens,
            "total_tokens": message.usage.total_tokens,
        }
    return stored


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
        "working_memory": _working_to_dict(chat.working_memory),
        "messages": [_message_to_dict(message) for message in chat.messages],
    }


def _chat_from_dict(payload: dict) -> Chat:
    return Chat(
        id=payload["id"],
        title=payload["title"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        messages=[_message_from_dict(item) for item in payload.get("messages", [])],
        working_memory=_working_from_dict(payload.get("working_memory")),
    )


def _entry_to_dict(entry: LongTermEntry) -> dict:
    return {
        "id": entry.id,
        "text": entry.text,
        "source_chat_id": entry.source_chat_id,
        "created_at": entry.created_at,
    }


def _entry_from_dict(payload: dict) -> LongTermEntry:
    return LongTermEntry(
        id=payload["id"],
        text=payload["text"],
        source_chat_id=payload.get("source_chat_id", ""),
        created_at=payload.get("created_at", ""),
    )


def _candidate_to_dict(candidate: MemoryCandidate) -> dict:
    return {
        "id": candidate.id,
        "text": candidate.text,
        "category": candidate.category,
        "source_chat_id": candidate.source_chat_id,
        "status": candidate.status,
        "created_at": candidate.created_at,
    }


def _candidate_from_dict(payload: dict) -> MemoryCandidate:
    return MemoryCandidate(
        id=payload["id"],
        text=payload["text"],
        category=payload["category"],
        source_chat_id=payload.get("source_chat_id", ""),
        status=payload.get("status", "pending"),
        created_at=payload.get("created_at", ""),
    )