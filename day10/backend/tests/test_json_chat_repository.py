import json

import pytest

from app.domain.models import ChatNotFound, ChatPersistenceError, TokenUsage
from app.infrastructure.json_chat_repository import JsonChatRepository


@pytest.mark.asyncio
async def test_create_chat_persists_empty_chat(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")

    chat = await repository.create_chat()

    assert chat.title == "Новый чат"
    assert chat.messages == []
    data = json.loads((tmp_path / "chats.json").read_text())
    assert data["version"] == 1
    stored = data["chats"][0]
    assert stored["id"] == chat.id
    assert stored["title"] == "Новый чат"
    assert stored["active_branch_id"] == stored["branches"][0]["id"]
    assert stored["branches"][0]["name"] == "main"
    assert stored["branches"][0]["fork_at"] is None
    assert stored["branches"][0]["messages"] == []
    assert stored["branches"][0]["facts"] == {}


@pytest.mark.asyncio
async def test_exchange_survives_new_repository_instance(tmp_path):
    path = tmp_path / "chats.json"
    first = JsonChatRepository(path)
    chat = await first.create_chat()

    await first.append_exchange(
        chat.id,
        "Меня зовут Анна",
        "Приятно познакомиться",
        TokenUsage(10, 5, 15),
    )

    second = JsonChatRepository(path)
    restored = await second.get_chat(chat.id)

    assert [message.role for message in restored.messages] == ["user", "assistant"]
    assert [message.content for message in restored.messages] == [
        "Меня зовут Анна",
        "Приятно познакомиться",
    ]
    assert restored.title == "Меня зовут Анна"


@pytest.mark.asyncio
async def test_unknown_chat_raises_chat_not_found(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")

    with pytest.raises(ChatNotFound):
        await repository.get_chat("missing")


@pytest.mark.asyncio
async def test_malformed_json_raises_persistence_error(tmp_path):
    path = tmp_path / "chats.json"
    path.write_text("not-json")
    repository = JsonChatRepository(path)

    with pytest.raises(ChatPersistenceError):
        await repository.list_chats()


@pytest.mark.asyncio
async def test_delete_chat_removes_chat_from_storage(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")
    chat = await repository.create_chat()

    await repository.delete_chat(chat.id)

    assert await repository.list_chats() == []
    with pytest.raises(ChatNotFound):
        await repository.get_chat(chat.id)


@pytest.mark.asyncio
async def test_long_first_message_gets_readable_short_title(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")
    chat = await repository.create_chat()
    message = (
        "Как объяснить архитектуру приложения, которое должно сохранять "
        "историю диалогов между перезапусками?"
    )

    await repository.append_exchange(
        chat.id, message, "Ответ", TokenUsage(10, 5, 15)
    )
    restored = await repository.get_chat(chat.id)

    assert restored.title == "Как объяснить архитектуру приложения…"


@pytest.mark.asyncio
async def test_assistant_message_persists_and_restores_usage(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")
    chat = await repository.create_chat()
    usage = TokenUsage(prompt_tokens=33, completion_tokens=7, total_tokens=40)

    await repository.append_exchange(chat.id, "Вопрос", "Ответ", usage)

    restored = await JsonChatRepository(tmp_path / "chats.json").get_chat(chat.id)
    assert restored.messages[0].usage is None
    assert restored.messages[1].usage == usage


@pytest.mark.asyncio
async def test_storage_without_usage_field_loads_none(tmp_path):
    path = tmp_path / "chats.json"
    path.write_text(
        '{"version": 1, "chats": [{"id": "chat-1", "title": "Т", '
        '"created_at": "2026-09-14T00:00:00+00:00", '
        '"updated_at": "2026-09-14T00:00:00+00:00", '
        '"messages": [{"role": "assistant", "content": "ok"}]}]}',
        encoding="utf-8",
    )

    chat = await JsonChatRepository(path).get_chat("chat-1")

    assert chat.messages[0].usage is None


@pytest.mark.asyncio
async def test_legacy_flat_chat_migrates_to_main_branch(tmp_path):
    path = tmp_path / "chats.json"
    path.write_text(json.dumps({"version": 1, "chats": [{
        "id": "old", "title": "T",
        "created_at": "2026-09-14T00:00:00+00:00",
        "updated_at": "2026-09-14T00:00:00+00:00",
        "messages": [{"role": "user", "content": "привет"}],
    }]}, ensure_ascii=False), encoding="utf-8")
    repository = JsonChatRepository(path)

    chat = await repository.get_chat("old")

    assert [branch.name for branch in chat.branches] == ["main"]
    assert chat.active_branch_id == chat.branches[0].id
    assert chat.messages[0].content == "привет"
    assert chat.facts == {}


@pytest.mark.asyncio
async def test_append_exchange_targets_active_branch(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")
    chat = await repository.create_chat()

    updated = await repository.append_exchange(
        chat.id, "u", "a", TokenUsage(1, 1, 2)
    )

    assert updated.active_branch.messages[-1].content == "a"
    assert len(updated.branches) == 1


@pytest.mark.asyncio
async def test_fork_branch_copies_prefix_and_inherits_facts(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")
    chat = await repository.create_chat()
    for i in range(4):
        chat = await repository.append_exchange(
            chat.id, f"u{i}", f"a{i}", TokenUsage(1, 1, 2)
        )
    chat = await repository.save_facts(
        chat.id, chat.active_branch_id, {"цель": "ТЗ"}
    )

    forked = await repository.fork_branch(chat.id, 3, "ветка Б")

    assert len(forked.branches) == 2
    branch_b = forked.active_branch
    assert branch_b.name == "ветка Б"
    assert branch_b.fork_at == 3
    assert [m.content for m in branch_b.messages if m.role == "user"] == ["u0", "u1"]
    assert branch_b.facts == {"цель": "ТЗ"}
    assert len(forked.branches[0].messages) == 8


@pytest.mark.asyncio
async def test_fork_branch_index_out_of_range(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")
    chat = await repository.create_chat()
    chat = await repository.append_exchange(chat.id, "u", "a", TokenUsage(1, 1, 2))

    with pytest.raises(IndexError):
        await repository.fork_branch(chat.id, 99, "x")


@pytest.mark.asyncio
async def test_switch_and_delete_branch(tmp_path):
    from app.domain.models import BranchNotFound, LastBranchError

    repository = JsonChatRepository(tmp_path / "chats.json")
    chat = await repository.create_chat()
    chat = await repository.append_exchange(chat.id, "u", "a", TokenUsage(1, 1, 2))
    chat = await repository.fork_branch(chat.id, 2, "Б")
    main = next(b for b in chat.branches if b.name == "main")

    chat = await repository.set_active_branch(chat.id, main.id)
    assert chat.active_branch_id == main.id

    branch_b = next(b.id for b in chat.branches if b.id != main.id)
    chat = await repository.delete_branch(chat.id, branch_b)
    assert len(chat.branches) == 1

    with pytest.raises(LastBranchError):
        await repository.delete_branch(chat.id, chat.branches[0].id)
    with pytest.raises(BranchNotFound):
        await repository.set_active_branch(chat.id, "нет-такой")


@pytest.mark.asyncio
async def test_facts_survive_restart(tmp_path):
    path = tmp_path / "chats.json"
    repository = JsonChatRepository(path)
    chat = await repository.create_chat()
    await repository.save_facts(chat.id, chat.active_branch_id, {"a": "1"})

    reloaded = await JsonChatRepository(path).get_chat(chat.id)

    assert reloaded.facts == {"a": "1"}


@pytest.mark.asyncio
async def test_append_exchange_into_inactive_branch(tmp_path):
    repository = JsonChatRepository(tmp_path / "chats.json")
    chat = await repository.create_chat()
    chat = await repository.append_exchange(chat.id, "u", "a", TokenUsage(1, 1, 2))
    chat = await repository.fork_branch(chat.id, 0, "Б")
    main_id = chat.branches[0].id

    updated = await repository.append_exchange(
        chat.id, "u2", "a2", TokenUsage(1, 1, 2), branch_id=main_id
    )

    assert [m.content for m in updated.branches[0].messages] == [
        "u", "a", "u2", "a2"
    ]
    assert updated.active_branch.messages == []
