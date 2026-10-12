from app.domain.models import ChatMessage, ChatState, Role
from app.infrastructure.chat_store import JsonChatStore


def test_save_load_delete(tmp_path):
    store = JsonChatStore(tmp_path / "chats")
    assert store.load(7) is None
    st = ChatState(chat_id=7, system_prompt="s", model="gemma4:12b")
    st.messages.append(ChatMessage(Role.USER, "hi"))
    store.save(st)
    loaded = store.load(7)
    assert loaded.chat_id == 7 and loaded.history()[0].content == "hi"
    assert loaded.updated_at
    assert store.list_ids() == [7]
    store.delete(7)
    assert store.load(7) is None
