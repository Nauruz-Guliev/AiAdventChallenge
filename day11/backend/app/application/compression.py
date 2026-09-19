from typing import Sequence

from app.domain.models import ChatMessage

SUMMARIZER_SYSTEM_PROMPT = (
    "You compress dialogue history into a terse, factual summary. "
    "Write in the same language as the dialogue. Preserve: the user's goals "
    "and constraints, established facts, decisions taken, open questions, "
    "exact names and numbers. No commentary, no invented details."
)


def split_history(
    messages: Sequence[ChatMessage], keep_recent: int
) -> tuple[list[ChatMessage], list[ChatMessage]]:
    if len(messages) <= keep_recent:
        return [], list(messages)
    return list(messages[:-keep_recent]), list(messages[-keep_recent:])


def build_summarization_messages(
    summary: str | None,
    old_messages: Sequence[ChatMessage],
    max_tokens: int,
) -> list[ChatMessage]:
    transcript = "\n".join(
        f"{message.role}: {message.content}" for message in old_messages
    )
    user_prompt = (
        f"Предыдущая свёртка диалога: {summary or 'нет'}.\n\n"
        f"Сообщения для сжатия:\n{transcript}\n\n"
        f"Обнови краткое содержание диалога, уложившись примерно в {max_tokens} токенов."
    )
    return [
        ChatMessage(role="system", content=SUMMARIZER_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]


def build_summary_message(summary: str, covered: int) -> ChatMessage:
    return ChatMessage(
        role="system",
        content=f"Краткое содержание предыдущих {covered} сообщений диалога:\n{summary}",
    )
