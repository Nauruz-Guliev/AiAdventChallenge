import json

import pytest

from app.domain.models import ChatNotFound, ChatPersistenceError
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

    await first.append_exchange(chat.id, "Меня зовут Анна", "Приятно познакомиться")

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
