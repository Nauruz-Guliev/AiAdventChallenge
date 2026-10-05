from __future__ import annotations

import json
import re

from app.domain.models import TaskMemory

MEMORY_SYSTEM = (
    "MEMORY Ты ведёшь память задачи диалога. На основе текущей памяти, вопроса и ответа "
    "верни обновлённую память ТОЛЬКО как JSON: "
    '{"goal": str, "clarifications": [str], "constraints": [str], "terms": [str]}. '
    "Не теряй уже зафиксированную информацию, добавляй только новое."
)


def build_memory_prompt(memory: TaskMemory) -> str:
    return "Память задачи:\n" + json.dumps(memory.to_dict(), ensure_ascii=False, indent=2)


def _extract_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except ValueError:
        return None


def parse_memory(reply: str) -> TaskMemory:
    data = _extract_json(reply)
    if data is None:
        return TaskMemory()
    return TaskMemory.from_dict(data)


def _union(old: list[str], new: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in list(old) + list(new):
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def merge_memory(old: TaskMemory, new: TaskMemory) -> TaskMemory:
    return TaskMemory(
        goal=(new.goal or old.goal).strip(),
        clarifications=_union(old.clarifications, new.clarifications),
        constraints=_union(old.constraints, new.constraints),
        terms=_union(old.terms, new.terms),
    )
