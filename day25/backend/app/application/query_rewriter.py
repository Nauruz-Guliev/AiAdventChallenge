from __future__ import annotations

from app.ports.llm_gateway import LLMGateway

REWRITE_SYSTEM = (
    "Переформулируй вопрос пользователя в короткий англоязычный поисковый запрос "
    "из ключевых терминов Kotlin Multiplatform. Верни только запрос, без пояснений."
)


class QueryRewriter:
    def __init__(self, gateway: LLMGateway, enabled: bool = True, system: str = REWRITE_SYSTEM):
        self._gateway = gateway
        self._enabled = enabled
        self._system = system

    async def rewrite(self, question: str) -> str:
        if not self._enabled:
            return question
        reply = await self._gateway.complete([
            {"role": "system", "content": self._system},
            {"role": "user", "content": question},
        ])
        cleaned = " ".join((reply or "").split()).strip()
        return cleaned or question
