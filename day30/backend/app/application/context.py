from __future__ import annotations

from app.domain.models import ChatMessage, ContextBudgetExceeded, InvalidRequest


def estimate_tokens(text: str) -> int:
    """Грубая оценка токенов: примерно 4 символа на токен."""
    if not text:
        return 0
    return (len(text) + 3) // 4


def messages_tokens(messages: list[ChatMessage]) -> int:
    return sum(estimate_tokens(m.content) + 4 for m in messages)


def clamp_max_tokens(requested: int | None, default: int, limit: int) -> int:
    value = default if requested is None else requested
    if value < 1:
        raise InvalidRequest("max_tokens должен быть >= 1")
    return min(value, limit)


def check_budget(messages: list[ChatMessage], max_tokens: int, num_ctx: int) -> int:
    prompt = messages_tokens(messages)
    if prompt + max_tokens > num_ctx:
        raise ContextBudgetExceeded(
            f"Промпт ~{prompt} токенов + max_tokens {max_tokens} превышает num_ctx {num_ctx}. "
            "Сократи историю или уменьши max_tokens."
        )
    return prompt
