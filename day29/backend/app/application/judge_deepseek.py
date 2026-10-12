from __future__ import annotations

import json
import re

from app.domain.models import ChatMessage, Role
from app.ports.llm import LLM

JUDGE_SYSTEM = (
    "Ты — строгий, но справедливый оценщик ответов на вопросы по Kotlin Multiplatform. "
    "Тебе дают ВОПРОС, ЭТАЛОН (что должно быть в ответе) и ОТВЕТ. Оцени, насколько ОТВЕТ "
    "соответствует ЭТАЛОНУ и отвечает на ВОПРОС, по шкале от 0 до 1 (0 — неверно/пусто, "
    "1 — полностью верно). Верни ТОЛЬКО JSON: {\"score\": <число>, \"reason\": \"<кратко>\"}."
)

_FLOAT = re.compile(r"-?\d+(?:\.\d+)?")


def parse_score(text: str) -> float:
    text = (text or "").strip()
    try:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            obj = json.loads(text[start : end + 1])
            return max(0.0, min(1.0, float(obj.get("score", 0.0))))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    m = _FLOAT.search(text)
    if not m:
        return 0.0
    try:
        return max(0.0, min(1.0, float(m.group(0))))
    except ValueError:
        return 0.0


class DeepSeekJudge:
    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    async def score(self, question: str, expectation: str, answer: str) -> float:
        user = f"ВОПРОС:\n{question}\n\nЭТАЛОН:\n{expectation}\n\nОТВЕТ:\n{answer}"
        completion = await self._llm.complete([
            ChatMessage(Role.SYSTEM, JUDGE_SYSTEM),
            ChatMessage(Role.USER, user),
        ])
        return parse_score(completion.text)
