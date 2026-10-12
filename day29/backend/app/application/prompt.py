from __future__ import annotations

from app.domain.models import ChatMessage, Hit, Role

RAG_SYSTEM = (
    "Ты — ассистент по Kotlin Multiplatform. Отвечай на русском, опираясь на КОНТЕКСТ "
    "(выдержки из документации). Каждый факт помечай ссылкой [n], где n — номер блока "
    "контекста. Не ссылайся на блоки, которые не используешь. Если в контексте нет ответа — "
    "честно скажи, что не нашёл, и не выдумывай."
)

NO_RAG_SYSTEM = (
    "Ты — ассистент по Kotlin Multiplatform. Отвечай на русском кратко и по делу."
)

NO_ANSWER_TEXT = (
    "Я не нашёл достаточно релевантного материала в базе, чтобы ответить. "
    "Уточни, пожалуйста, вопрос."
)


def build_context(hits: list[Hit]) -> str:
    blocks = [f"[{i}] {h.source} :: {h.section}\n{h.text}" for i, h in enumerate(hits, 1)]
    return "\n\n".join(blocks)


def build_messages(
    history: list[ChatMessage],
    context: str,
    question: str,
    system: str = RAG_SYSTEM,
) -> list[ChatMessage]:
    user = f"Контекст:\n{context}\n\nВопрос: {question}" if context else question
    return [ChatMessage(Role.SYSTEM, system), *history, ChatMessage(Role.USER, user)]
