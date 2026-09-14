from app.domain.models import ChatMessage
from app.infrastructure.token_counter import PER_MESSAGE_OVERHEAD_TOKENS, TiktokenCounter


def test_count_text_returns_zero_for_empty_string():
    assert TiktokenCounter().count_text("") == 0


def test_count_text_counts_known_english_phrase():
    assert TiktokenCounter().count_text("hello world") == 2


def test_count_text_counts_russian_text_more_than_words():
    assert TiktokenCounter().count_text("сколько стоит контекст") > 4


def test_count_messages_adds_per_message_overhead():
    counter = TiktokenCounter()
    messages = [
        ChatMessage(role="system", content="hello world"),
        ChatMessage(role="user", content="hello world"),
    ]

    assert counter.count_messages(messages) == 2 * (
        2 + PER_MESSAGE_OVERHEAD_TOKENS
    )
