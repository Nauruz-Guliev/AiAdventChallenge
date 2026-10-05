from __future__ import annotations

from app.application.citation import extract_citations
from app.application.memory import (
    MEMORY_SYSTEM,
    build_memory_prompt,
    merge_memory,
    parse_memory,
)
from app.domain.models import ChatTurn, Hit, InvalidQuestion, Message, Session, TaskMemory
from app.infrastructure.heuristic_reranker import filter_by_threshold
from app.ports.llm_gateway import LLMGateway
from app.ports.reranker import Reranker
from app.ports.retriever import Retriever
from app.ports.rewriter import Rewriter

CHAT_SYSTEM = (
    "Ты — ассистент по Kotlin Multiplatform. Отвечай на вопрос, используя приведённый "
    "контекст как основной источник, учитывай ПАМЯТЬ ЗАДАЧИ (цель, уточнения, ограничения) "
    "и историю диалога. Не теряй цель диалога. Каждый факт в ответе помечай ссылкой [n], "
    "где n — номер блока контекста. Не ссылайся на блоки, которые не используешь."
)

NO_ANSWER_TEXT = (
    "Я не нашёл достаточно релевантного материала, чтобы ответить. "
    "Уточните, пожалуйста, вопрос."
)


def _build_history(messages: list[Message]) -> str:
    lines = []
    for m in messages[-20:]:
        role = "Пользователь" if m.role == "user" else "Ассистент"
        lines.append(f"{role}: {m.text}")
    return "\n".join(lines) if lines else "(нет истории)"


def _build_context(hits: list[Hit]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(f"[{i}] {h.source} :: {h.section}\n{h.text}")
    return "\n\n".join(blocks)


class ChatService:
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
        no_answer_min_score: float = 0.60,
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

    async def answer(self, session: Session, text: str) -> ChatTurn:
        text = (text or "").strip()
        if not text:
            raise InvalidQuestion("Вопрос не может быть пустым")

        rewrite_input = text
        if session.memory.goal:
            rewrite_input = f"Цель: {session.memory.goal}\nВопрос: {text}"
        query = await self._rewriter.rewrite(rewrite_input)

        hits = self._retriever.search(query, top_k=self.k_pre)
        hits = self._reranker.rerank(query, hits)
        hits = filter_by_threshold(hits, self.min_sim, self.k_post)

        if not hits:
            return ChatTurn(
                reply=NO_ANSWER_TEXT, sources=(), citations=(),
                memory=session.memory, answerable=False, relevance=0.0,
            )

        relevance = round(
            max((self._retriever.similarity(text, h.chunk_id) for h in hits), default=0.0),
            3,
        )
        if relevance < self.no_answer_min_score:
            return ChatTurn(
                reply=NO_ANSWER_TEXT, sources=(), citations=(),
                memory=session.memory, answerable=False, relevance=relevance,
            )

        context = _build_context(hits)
        user_prompt = (
            f"{build_memory_prompt(session.memory)}\n\n"
            f"История диалога:\n{_build_history(session.messages)}\n\n"
            f"Контекст:\n{context}\n\n"
            f"Вопрос: {text}"
        )
        reply = await self._gateway.complete([
            {"role": "system", "content": CHAT_SYSTEM},
            {"role": "user", "content": user_prompt},
        ])
        citations = tuple(extract_citations(reply, hits, self.min_quote_len))

        new_memory = await self._update_memory(session.memory, text, reply)
        return ChatTurn(
            reply=reply, sources=tuple(hits), citations=citations,
            memory=new_memory, answerable=True, relevance=relevance,
        )

    async def _update_memory(self, memory: TaskMemory, question: str, answer: str) -> TaskMemory:
        reply = await self._gateway.complete([
            {"role": "system", "content": MEMORY_SYSTEM},
            {"role": "user", "content": (
                f"{build_memory_prompt(memory)}\n\nВопрос: {question}\nОтвет: {answer}"
            )},
        ])
        return merge_memory(memory, parse_memory(reply))
