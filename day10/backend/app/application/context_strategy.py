import json
import re

from app.domain.models import Branch, ChatMessage, UsageConfig

CONTEXT_MODES = ("full", "sliding", "facts", "branching")

FACTS_UPDATER_SYSTEM_PROMPT = (
    "You maintain a compact key-value facts memory of a dialogue in Russian. "
    "Given current facts (JSON) and the newest user message, return the FULL "
    "updated facts JSON: goals, constraints, preferences, decisions, "
    "agreements, numbers, names. Keep keys short Russian labels. Merge, do "
    "not duplicate. Output only a JSON object, no prose."
)


def build_facts_message(facts):
    if not facts:
        return None
    lines = "\n".join(f"- {key}: {value}" for key, value in sorted(facts.items()))
    return ChatMessage(
        role="system", content=f"Известные факты о задаче:\n{lines}"
    )


def assemble_history(mode, branch, new_message, config):
    if mode not in CONTEXT_MODES:
        raise ValueError(f"Unknown context mode: {mode}")
    if mode in ("full", "branching"):
        return [*branch.messages, new_message]
    window = config.sliding_window_messages
    if mode == "sliding":
        return [*branch.messages[-window:], new_message]
    facts_message = build_facts_message(branch.facts)
    history = branch.messages[-window:]
    if facts_message is None:
        return [*history, new_message]
    return [facts_message, *history, new_message]


def build_facts_update_messages(facts, user_text, limit):
    user_prompt = (
        f"Текущие факты:\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        f"Новое сообщение пользователя:\n{user_text}\n\n"
        f"Верни обновлённые факты JSON (не больше {limit} записей)."
    )
    return [
        ChatMessage(role="system", content=FACTS_UPDATER_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]


def parse_facts_update(raw_text, limit):
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    cleaned = {str(key): str(value) for key, value in data.items()}
    return dict(list(cleaned.items())[:limit])
