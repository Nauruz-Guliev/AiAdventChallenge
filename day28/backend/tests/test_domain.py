from app.domain.models import ChatMessage, ChatState, GenerationStats, Role


def test_tokens_per_second():
    s = GenerationStats(model="m", completion_tokens=100, eval_duration_ns=2_000_000_000)
    assert round(s.tokens_per_second) == 50


def test_chatstate_roundtrip():
    st = ChatState(chat_id=1, system_prompt="sys", model="gemma4:12b")
    st.rag_enabled = False
    st.think = True
    st.last_question = "q?"
    st.messages.append(ChatMessage(Role.USER, "hi"))
    st2 = ChatState.from_dict(st.to_dict())
    assert st2.chat_id == 1 and st2.rag_enabled is False and st2.think is True
    assert st2.last_question == "q?"
    assert st2.history()[0].content == "hi"


def test_chatmessage_to_ollama():
    assert ChatMessage(Role.SYSTEM, "x").to_ollama() == {"role": "system", "content": "x"}
