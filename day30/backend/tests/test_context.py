import pytest

from app.application.context import (
    check_budget,
    clamp_max_tokens,
    estimate_tokens,
    messages_tokens,
)
from app.domain.models import ChatMessage, ContextBudgetExceeded, InvalidRequest


def test_estimate_tokens_empty_is_zero():
    assert estimate_tokens("") == 0


def test_estimate_tokens_is_about_quarter_of_chars():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10


def test_messages_tokens_adds_overhead_per_message():
    msgs = [ChatMessage("user", "abcd"), ChatMessage("assistant", "abcd")]
    assert messages_tokens(msgs) == 2 * (1 + 4)


def test_clamp_max_tokens_uses_default_and_limit():
    assert clamp_max_tokens(None, 512, 2048) == 512
    assert clamp_max_tokens(9999, 512, 2048) == 2048
    assert clamp_max_tokens(100, 512, 2048) == 100


def test_clamp_max_tokens_rejects_non_positive():
    with pytest.raises(InvalidRequest):
        clamp_max_tokens(0, 512, 2048)


def test_check_budget_returns_prompt_tokens():
    msgs = [ChatMessage("user", "a" * 40)]
    assert check_budget(msgs, 100, 8192) == 10 + 4


def test_check_budget_raises_when_over():
    msgs = [ChatMessage("user", "a" * 4000)]
    with pytest.raises(ContextBudgetExceeded):
        check_budget(msgs, 512, 1024)
