from app.application.compression import (
    build_summarization_messages,
    build_summary_message,
    split_history,
)
from app.domain.models import ChatMessage


def make_history(count: int) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for index in range(count):
        messages.append(ChatMessage(role="user", content=f"вопрос {index}"))
        messages.append(ChatMessage(role="assistant", content=f"ответ {index}"))
    return messages


def test_split_history_keeps_recent_tail():
    history = make_history(8)
    old, recent = split_history(history, keep_recent=10)
    assert recent == history[-10:]
    assert old == history[:-10]


def test_split_history_short_dialog_has_no_old_part():
    history = make_history(3)
    old, recent = split_history(history, keep_recent=10)
    assert old == []
    assert recent == history


def test_summarization_messages_shape():
    old = make_history(2)
    messages = build_summarization_messages("прошлая свёртка", old, max_tokens=500)
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert "прошлая свёртка" in messages[1].content
    assert "вопрос 0" in messages[1].content
    assert "500" in messages[1].content


def test_summarization_messages_without_previous_summary():
    messages = build_summarization_messages(None, make_history(1), max_tokens=500)
    assert "нет" in messages[1].content


def test_build_summary_message():
    message = build_summary_message("Кратко: о X.", 12)
    assert message.role == "system"
    assert "12" in message.content
    assert "Кратко: о X." in message.content
