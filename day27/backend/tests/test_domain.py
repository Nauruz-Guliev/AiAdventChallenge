from app.domain.models import ChatMessage, ChatState, GenerationStats, Role


def test_message_to_ollama_with_image():
    m = ChatMessage(role=Role.USER, content="что тут?", images=["AAA"])
    assert m.to_ollama() == {"role": "user", "content": "что тут?", "images": ["AAA"]}


def test_message_to_dict_drops_images():
    m = ChatMessage(role=Role.USER, content="[фото]", images=["AAA"])
    assert m.to_dict() == {"role": "user", "content": "[фото]"}


def test_tokens_per_second():
    s = GenerationStats(model="m", completion_tokens=100, eval_duration_ns=2_000_000_000)
    assert abs(s.tokens_per_second - 50.0) < 1e-9


def test_tokens_per_second_zero_when_no_data():
    assert GenerationStats(model="m").tokens_per_second == 0.0


def test_chat_state_roundtrip():
    st = ChatState(chat_id=42, system_prompt="sys", model="m", messages=[
        ChatMessage(Role.USER, "hi"),
        ChatMessage(Role.ASSISTANT, "hello"),
    ])
    d = st.to_dict()
    assert d["chat_id"] == 42
    assert d["messages"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    back = ChatState.from_dict(d)
    assert back.chat_id == 42
    assert back.system_prompt == "sys"
    assert [m.content for m in back.messages] == ["hi", "hello"]


def test_history_excludes_system():
    st = ChatState(chat_id=1, system_prompt="s", model="m")
    assert st.history() == []
