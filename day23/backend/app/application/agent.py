from __future__ import annotations

from typing import Literal

from app.domain.models import Answer, Hit, InvalidQuestion
from app.ports.llm_gateway import LLMGateway
from app.ports.retriever import Retriever

NO_RAG_SYSTEM = (
    "Ты — ассистент по Kotlin Multiplatform. Отвечай кратко и по делу, "
    "опираясь на свои знания."
)

RAG_SYSTEM = (
    "Ты — ассистент по Kotlin Multiplatform. Отвечай на вопрос, используя "
    "приведённый контекст как основной источник. Опирайся на факты из контекста "
    "и в конце перечисли использованные источники (файл/секция). Если контекста "
    "не хватает, можешь дополнить ответ своими знаниями, но пометь, что это "
    "общие знания."
)


def build_context(hits: list[Hit]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(f"[{i}] {h.source} :: {h.section}\n{h.text}")
    return "\n\n".join(blocks)


class RAGAgent:
    def __init__(self, gateway: LLMGateway, retriever: Retriever, top_k: int = 4):
        self._gateway = gateway
        self._retriever = retriever
        self.top_k = top_k

    async def answer(self, question: str, mode: Literal["no_rag", "rag"] = "rag") -> Answer:
        text = (question or "").strip()
        if not text:
            raise InvalidQuestion("Вопрос не может быть пустым")

        if mode == "no_rag":
            reply = await self._gateway.complete([
                {"role": "system", "content": NO_RAG_SYSTEM},
                {"role": "user", "content": text},
            ])
            return Answer(mode="no_rag", text=reply, sources=())

        hits = self._retriever.search(text, top_k=self.top_k)
        context = build_context(hits)
        reply = await self._gateway.complete([
            {"role": "system", "content": RAG_SYSTEM},
            {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос: {text}"},
        ])
        return Answer(mode="rag", text=reply, sources=tuple(hits))
