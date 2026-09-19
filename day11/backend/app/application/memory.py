import json
import re

from app.domain.models import (
    LONG_TERM_CATEGORIES,
    Chat,
    ChatMessage,
    LongTermMemory,
    WorkingMemory,
)

CATEGORY_LABELS = {
    "profile": "профиль",
    "decisions": "решения",
    "knowledge": "знания",
}
MEMORY_COMMAND_PREFIXES = ("запомни:", "запомни, что", "запомни что")
DEFAULT_CATEGORY = "knowledge"

CANDIDATE_SYSTEM_PROMPT = (
    "Ты извлекаешь кандидатов в долговременную память ассистента. "
    "Долговременная память хранит только устойчивые данные: профиль пользователя "
    "(profile: имя, роль, язык, привычки), принятые решения (decisions: «используем "
    "PostgreSQL»), устойчивые знания и предпочтения (knowledge: «аллергия на арахис»). "
    "Не предлагай разовые детали диалога, приветствия и текущую задачу. "
    'Верни JSON-массив объектов {"text": str, "category": '
    '"profile"|"decisions"|"knowledge"}. Если нечего запоминать — верни []. '
    "Только JSON, без пояснений."
)


def build_long_term_block(long_term: LongTermMemory) -> ChatMessage | None:
    if long_term.total_count() == 0:
        return None
    lines: list[str] = []
    for category in LONG_TERM_CATEGORIES:
        entries = long_term.entries(category)
        if not entries:
            continue
        lines.append(f"{CATEGORY_LABELS[category]}:")
        lines.extend(f"- {item.text}" for item in entries)
    return ChatMessage(
        role="system",
        content="## Долговременная память (глобальная)\n" + "\n".join(lines),
    )


def build_working_block(working: WorkingMemory) -> ChatMessage | None:
    if working.status == "done" or working.is_empty:
        return None
    lines: list[str] = []
    if working.goal.strip():
        lines.append(f"Цель: {working.goal.strip()}")
    if working.constraints:
        lines.append("Ограничения:")
        lines.extend(f"- {item}" for item in working.constraints)
    if working.decisions:
        lines.append("Решения:")
        lines.extend(f"- {item}" for item in working.decisions)
    return ChatMessage(
        role="system",
        content="## Рабочая память (текущая задача)\n" + "\n".join(lines),
    )


def build_prompt(
    chat: Chat, long_term: LongTermMemory, system_prompt: str
) -> list[ChatMessage]:
    messages = [ChatMessage(role="system", content=system_prompt)]
    long_term_block = build_long_term_block(long_term)
    if long_term_block is not None:
        messages.append(long_term_block)
    working_block = build_working_block(chat.working_memory)
    if working_block is not None:
        messages.append(working_block)
    messages.extend(chat.messages)
    return messages


def parse_memory_command(text: str) -> str | None:
    stripped = text.strip()
    lowered = stripped.lower()
    for prefix in MEMORY_COMMAND_PREFIXES:
        if lowered.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def build_candidate_messages(
    user_text: str,
    answer: str,
    long_term: LongTermMemory,
    limit: int,
) -> list[ChatMessage]:
    existing: list[str] = []
    for category in LONG_TERM_CATEGORIES:
        existing.extend(item.text for item in long_term.entries(category))
    user_prompt = (
        "Уже сохранено в долговременной памяти:\n"
        + (json.dumps(existing, ensure_ascii=False) if existing else "[]")
        + f"\n\nНовое сообщение пользователя:\n{user_text}\n\n"
        + f"Ответ ассистента:\n{answer}\n\n"
        + f"Верни не больше {limit} новых кандидатов."
    )
    return [
        ChatMessage(role="system", content=CANDIDATE_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]


def parse_candidates(raw_text: str, limit: int) -> list[dict]:
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    result: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        category = str(item.get("category", "")).strip()
        if not text or category not in LONG_TERM_CATEGORIES:
            continue
        result.append({"text": text, "category": category})
        if len(result) >= limit:
            break
    return result


def parse_command_category(raw_text: str) -> str:
    candidates = parse_candidates(raw_text, 1)
    if candidates:
        return candidates[0]["category"]
    return DEFAULT_CATEGORY