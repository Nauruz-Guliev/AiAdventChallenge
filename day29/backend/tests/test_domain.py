from app.domain.models import (
    ABReport,
    CellResult,
    ChatMessage,
    ChatState,
    GenerationStats,
    ResourceSample,
    Role,
)


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


def test_chatstate_profile_quant_roundtrip():
    st = ChatState(chat_id=1, system_prompt="", model="gemma4:12b", profile="baseline", quant="q8")
    st2 = ChatState.from_dict(st.to_dict())
    assert st2.profile == "baseline" and st2.quant == "q8"


def test_ab_report_holds_cells():
    cell = CellResult(
        "baseline", "q4", "b", 0.8, 0.0, 100.0, 0.0, 50.0, 10.0, 0.0, 1, False, ResourceSample()
    )
    rep = ABReport((cell,), 3, 1, True)
    assert rep.cells[0].label == "b" and rep.notes == ()


def test_chatmessage_to_ollama():
    assert ChatMessage(Role.SYSTEM, "x").to_ollama() == {"role": "system", "content": "x"}
