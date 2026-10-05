from __future__ import annotations

from app.application.citation import extract_citations
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
    "приведённый контекст как основной источник. Каждый факт в ответе помечай "
    "ссылкой [n], где n — номер блока контекста, из которого взят факт. "
    "Не ссылайся на блоки, которые не используешь. Если контекста не хватает, "
    "дополни своими знаниями и пометь это."
)

NO_ANSWER_TEXT = (
    "Я не нашёл достаточно релевантного материала, чтобы ответить. "
    "Уточните, пожалуйста, вопрос."
)


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
        min_quote_len: int = 24,
        no_answer_min_score: float = 0.50,
    ):
        self._gateway = gateway
        self._retriever = retriever
        self._reranker = reranker
        self._rewriter = rewriter
        self.k_pre = k_pre
        self.k_post = k_post
        self.min_sim = min_sim
        self.min_quote_len = min_quote_len
        self.no_answer_min_score = no_answer_min_score

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
            relevance = round(hits[0].score, 3) if hits else None
        else:  # rag_guard
            query = await self._rewriter.rewrite(text)
            hits = self._retriever.search(query, top_k=self.k_pre)
            hits = self._reranker.rerank(query, hits)
            hits = filter_by_threshold(hits, self.min_sim, self.k_post)
            relevance = round(
                max((self._retriever.similarity(text, h.chunk_id) for h in hits), default=0.0),
                3,
            )
            if relevance < self.no_answer_min_score:
                return Answer(
                    mode=mode, text=NO_ANSWER_TEXT, sources=(),
                    citations=(), answerable=False, relevance=relevance,
                )

        context = build_context(hits)
        reply = await self._gateway.complete([
            {"role": "system", "content": RAG_SYSTEM},
            {"role": "user", "content": f"Контекст:\n{context}\n\nВопрос: {text}"},
        ])
        citations = tuple(extract_citations(reply, hits, self.min_quote_len))
        return Answer(
            mode=mode, text=reply, sources=tuple(hits),
            citations=citations, relevance=relevance,
        )
