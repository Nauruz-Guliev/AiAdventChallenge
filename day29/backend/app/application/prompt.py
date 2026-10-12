from __future__ import annotations

from app.domain.models import ChatMessage, Hit, Role

BASELINE_SYSTEM = (
    "Ты — ассистент по Kotlin Multiplatform. Отвечай на русском, опираясь на КОНТЕКСТ "
    "(выдержки из документации). Каждый факт помечай ссылкой [n], где n — номер блока "
    "контекста. Не ссылайся на блоки, которые не используешь. Если в контексте нет ответа — "
    "честно скажи, что не нашёл, и не выдумывай."
)

OPTIMIZED_SYSTEM = (
    "Ты — справочный ассистент по Kotlin Multiplatform. Отвечай только по КОНТЕКСТУ.\n"
    "1) Кратко: 2–5 пунктов или короткий абзац, без вступлений и повторения вопроса.\n"
    "2) Каждый факт помечай ссылкой [n] на блок контекста.\n"
    "3) Не используй знания вне контекста, не выдумывай.\n"
    "4) Если ответа в контексте нет — ответь ровно: «Не нашёл в базе».\n"
    "5) Язык — русский; имена API и код — как в контексте."
)

PROMPTS = {"baseline": BASELINE_SYSTEM, "optimized": OPTIMIZED_SYSTEM}

# Совместимость с днём 28
RAG_SYSTEM = BASELINE_SYSTEM

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
    prompt_key: str = "baseline",
) -> list[ChatMessage]:
    system = PROMPTS.get(prompt_key, BASELINE_SYSTEM)
    user = f"Контекст:\n{context}\n\nВопрос: {question}" if context else question
    return [ChatMessage(Role.SYSTEM, system), *history, ChatMessage(Role.USER, user)]
