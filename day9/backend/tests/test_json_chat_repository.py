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
    assert json.loads((tmp_path / "chats.json").read_text()) == {
        "version": 1,
        "chats": [
            {
                "id": chat.id,
                "title": "Новый чат",
                "created_at": chat.created_at,
                "updated_at": chat.updated_at,
                "messages": [],
            }
        ],
    }


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
