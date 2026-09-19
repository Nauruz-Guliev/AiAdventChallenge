import pytest

from app.application.usage import WARNING_FILL_RATIO, build_dialog_usage, exchange_cost_usd
from app.domain.models import ChatMessage, TokenUsage, UsageConfig
from app.infrastructure.token_counter import TiktokenCounter


def msg(role, content, usage=None):
    return ChatMessage(role=role, content=content, usage=usage)


def test_exchange_cost_uses_worst_case_prices():
    usage = TokenUsage(
        prompt_tokens=1_000_000,
        completion_tokens=500_000,
        total_tokens=1_500_000,
    )

    cost = exchange_cost_usd(usage, UsageConfig())

    assert cost == pytest.approx(0.30 + 0.60)


def test_build_dialog_usage_accumulates_persisted_usage():
    messages = [
        msg("system", "Вы полезный ассистент."),
        msg("user", "Меня зовут Анна"),
        msg("assistant", "Приятно познакомиться", TokenUsage(50, 10, 60)),
        msg("user", "Как меня зовут?"),
        msg("assistant", "Вас зовут Анна.", TokenUsage(70, 12, 82)),
    ]

    dialog = build_dialog_usage(messages, TiktokenCounter(), UsageConfig())

    assert dialog.dialog_total_tokens == 142
    assert dialog.dialog_cost_usd == pytest.approx(
        exchange_cost_usd(TokenUsage(50, 10, 60), UsageConfig())
        + exchange_cost_usd(TokenUsage(70, 12, 82), UsageConfig())
    )
    assert dialog.history_tokens > 0
    assert dialog.context_limit == 8000
    assert dialog.context_remaining == 8000 - dialog.history_tokens
    assert dialog.warning is False


def test_build_dialog_usage_warns_near_limit():
    filler = "токен " * 4000
    messages = [msg("user", filler)]
    config = UsageConfig(context_limit_tokens=3000)

    dialog = build_dialog_usage(messages, TiktokenCounter(), config)

    assert dialog.history_tokens >= config.context_limit_tokens * WARNING_FILL_RATIO
    assert dialog.warning is True


def test_dialog_without_usage_has_zero_totals():
    messages = [msg("system", "Вы полезный ассистент."), msg("user", "Привет")]

    dialog = build_dialog_usage(messages, TiktokenCounter(), UsageConfig())

    assert dialog.dialog_total_tokens == 0
    assert dialog.dialog_cost_usd == 0.0
