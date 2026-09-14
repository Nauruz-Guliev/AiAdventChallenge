from app.application.ports.token_counter import TokenCounter
from app.domain.models import ChatMessage, DialogUsage, TokenUsage, UsageConfig

WARNING_FILL_RATIO = 0.8


def exchange_cost_usd(usage: TokenUsage, config: UsageConfig) -> float:
    return (
        usage.prompt_tokens * config.input_price_per_million
        + usage.completion_tokens * config.output_price_per_million
    ) / 1_000_000


def build_dialog_usage(
    messages: list[ChatMessage],
    counter: TokenCounter,
    config: UsageConfig,
) -> DialogUsage:
    history_tokens = counter.count_messages(messages)
    exchanges = [message.usage for message in messages if message.usage is not None]
    remaining = config.context_limit_tokens - history_tokens
    return DialogUsage(
        history_tokens=history_tokens,
        dialog_total_tokens=sum(usage.total_tokens for usage in exchanges),
        dialog_cost_usd=sum(exchange_cost_usd(usage, config) for usage in exchanges),
        context_limit=config.context_limit_tokens,
        context_remaining=max(remaining, 0),
        warning=history_tokens >= config.context_limit_tokens * WARNING_FILL_RATIO,
    )
