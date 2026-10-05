from __future__ import annotations

from app.domain.models import Answer, Hit, InvalidQuestion, Mode
from app.infrastructure.heuristic_reranker import filter_by_threshold
from app.ports.llm_gateway import LLMGateway
from app.ports.reranker import Reranker
from app.ports.retriever import Retriever
from app.ports.rewriter import Rewriter

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

_FILTER_MODES = ("rag_filter", "rag_full")
_REWRITE_MODES = ("rag_rewrite", "rag_full")


def build_context(hits: list[Hit]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(f"[{i}] {h.source} :: {h.section}\n{h.text}")
    return "\n\n".join(blocks)


class RAGAgent:
    def __init__(
        self,
        gateway: LLMGateway,
        retriever: Retriever,
        reranker: Reranker,
        rewriter: Rewriter,
        k_pre: int = 30,
        k_post: int = 8,
        min_sim: float = 0.35,
    ):
        self._gateway = gateway
        self._retriever = retriever
        self._reranker = reranker
        self._rewriter = rewriter
        self.k_pre = k_pre
        self.k_post = k_post
        self.min_sim = min_sim

    async def answer(self, question: str, mode: Mode = "rag") -> Answer:
        text = (question or "").strip()
        if not text:
            raise InvalidQuestion("Вопрос не может быть пустым")

        if mode == "no_rag":
            reply = await self._gateway.complete([
                {"role": "system", "content": NO_RAG_SYSTEM},
                {"role": "user", "content": text},
            ])
            return Answer(mode="no_rag", text=reply, sources=())

        if mode == "rag":
            hits = self._retriever.search(text, top_k=self.k_post)
        else:
            query = await self._rewriter.rewrite(text) if mode in _REWRITE_MODES else text
            if mode in _FILTER_MODES:
                hits = self._retriever.search(query, top_k=self.k_pre)
                hits = self._reranker.rerank(query, hits)
                hits = filter_by_threshold(hits, self.min_sim, self.k_post)
            else:
                hits = self._retriever.search(query, top_k=self.k_post)

        context = build_context(hits)
        reply = await self._gateway.complete([
            {"role": "system", "content": RAG_SYSTEM},
            {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос: {text}"},
        ])
        return Answer(mode=mode, text=reply, sources=tuple(hits))
