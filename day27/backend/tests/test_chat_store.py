from app.domain.models import ChatMessage, ChatState, Role
from app.infrastructure.chat_store import JsonChatStore


def test_save_load_roundtrip(tmp_path):
    store = JsonChatStore(tmp_path)
    st = ChatState(chat_id=42, system_prompt="sys", model="gemma4:12b",
                   messages=[ChatMessage(Role.USER, "hi"), ChatMessage(Role.ASSISTANT, "yo")])
    store.save(st)
    assert (tmp_path / "42.json").exists()
    back = store.load(42)
    assert back.system_prompt == "sys"
    assert [m.content for m in back.messages] == ["hi", "yo"]
    assert back.updated_at != ""


def test_load_missing_returns_none(tmp_path):
    assert JsonChatStore(tmp_path).load(7) is None


def test_delete_and_list(tmp_path):
    store = JsonChatStore(tmp_path)
    store.save(ChatState(chat_id=1, system_prompt="s", model="m"))
    store.save(ChatState(chat_id=2, system_prompt="s", model="m"))
    assert store.list_ids() == [1, 2]
    store.delete(1)
    assert store.list_ids() == [2]


def test_corrupt_file_returns_none(tmp_path):
    store = JsonChatStore(tmp_path)
    (tmp_path / "5.json").write_text("{ not json", encoding="utf-8")
    assert store.load(5) is None
