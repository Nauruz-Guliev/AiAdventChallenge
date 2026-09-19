import json

import pytest

from app.domain.models import (
    CandidateConflict,
    CandidateNotFound,
    ChatNotFound,
    ChatPersistenceError,
    LongTermEntryNotFound,
    LongTermMemory,
    TokenUsage,
    WorkingMemory,
)
from app.infrastructure.json_memory_repository import JsonMemoryRepository


def repo(tmp_path):
    return JsonMemoryRepository(
        chats_dir=tmp_path / "chats",
        long_term_path=tmp_path / "long_term.json",
        candidates_path=tmp_path / "candidates.json",
    )


@pytest.mark.asyncio
async def test_three_memory_types_live_in_separate_files(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    await repository.append_exchange(chat.id, "привет", "ответ", TokenUsage(1, 1, 2))
    await repository.add_long_term_entry("knowledge", "аллергия", chat.id)
    await repository.add_candidates(
        [{"text": "люблю Kotlin", "category": "profile"}], chat.id
    )

    assert (tmp_path / "chats" / f"{chat.id}.json").exists()
    assert (tmp_path / "long_term.json").exists()
    assert (tmp_path / "candidates.json").exists()
    chat_payload = json.loads((tmp_path / "chats" / f"{chat.id}.json").read_text())
    assert "working_memory" in chat_payload
    assert "knowledge" not in chat_payload


@pytest.mark.asyncio
async def test_chat_crud_and_clear_history(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    await repository.append_exchange(chat.id, "u", "a", TokenUsage(1, 1, 2))

    cleared = await repository.clear_messages(chat.id)

    assert cleared.messages == []
    assert (await repository.get_chat(chat.id)).messages == []
    assert [c.id for c in await repository.list_chats()] == [chat.id]
    await repository.delete_chat(chat.id)
    with pytest.raises(ChatNotFound):
        await repository.get_chat(chat.id)


@pytest.mark.asyncio
async def test_working_memory_persists_overwrite_and_lifecycle(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()

    await repository.save_working_memory(
        chat.id, WorkingMemory(goal="бюджет 500", constraints=["500"])
    )
    await repository.save_working_memory(
        chat.id, WorkingMemory(goal="бюджет 900", constraints=["900"])
    )
    reloaded = await repo(tmp_path).get_working_memory(chat.id)
    assert reloaded.goal == "бюджет 900"
    assert reloaded.constraints == ["900"]

    done = await repository.complete_working_memory(chat.id)
    assert done.working_memory.status == "done"

    reset = await repository.reset_working_memory(chat.id)
    assert reset.working_memory.is_empty
    assert reset.working_memory.status == "active"


@pytest.mark.asyncio
async def test_long_term_add_delete_duplicate(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    entry = await repository.add_long_term_entry("profile", "Науруз", chat.id)

    assert (await repository.get_long_term()).profile[0].text == "Науруз"
    with pytest.raises(CandidateConflict):
        await repository.add_long_term_entry("profile", "Науруз", chat.id)

    await repository.delete_long_term_entry("profile", entry.id)
    assert (await repository.get_long_term()).total_count() == 0
    with pytest.raises(LongTermEntryNotFound):
        await repository.delete_long_term_entry("profile", "missing")


@pytest.mark.asyncio
async def test_candidates_flow_approve_reject_and_dedup(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    await repository.add_candidates(
        [
            {"text": "аллергия", "category": "knowledge"},
            {"text": "аллергия", "category": "knowledge"},
            {"text": "Kotlin", "category": "profile"},
        ],
        chat.id,
    )
    pending = await repository.list_candidates("pending")
    assert [c.text for c in pending] == ["аллергия", "Kotlin"]

    entry = await repository.approve_candidate(pending[0].id)
    assert entry.text == "аллергия"
    assert (await repository.get_long_term()).knowledge[0].text == "аллергия"
    with pytest.raises(CandidateConflict):
        await repository.approve_candidate(pending[0].id)

    await repository.reject_candidate(pending[1].id)
    assert [c.text for c in await repository.list_candidates("pending")] == []
    assert await repository.clear_rejected_candidates() == 1
    with pytest.raises(CandidateNotFound):
        await repository.reject_candidate("missing")


@pytest.mark.asyncio
async def test_malformed_chat_file_raises_persistence_error(tmp_path):
    repository = repo(tmp_path)
    chat = await repository.create_chat()
    (tmp_path / "chats" / f"{chat.id}.json").write_text("not-json")

    with pytest.raises(ChatPersistenceError):
        await repository.get_chat(chat.id)