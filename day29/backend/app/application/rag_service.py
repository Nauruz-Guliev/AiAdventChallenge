from __future__ import annotations

from dataclasses import dataclass

from app.application.citation import extract_citations
from app.application.prompt import (
    NO_ANSWER_TEXT,
    NO_RAG_SYSTEM,
    build_context,
    build_messages,
)
from app.config import Settings
from app.domain.models import ChatMessage, GenerationStats, Hit, RagAnswer
from app.infrastructure.heuristic_reranker import filter_by_threshold
from app.ports.llm import LLM


@dataclass
class Prepared:
    messages: list[ChatMessage]
    hits: list[Hit]
    relevance: float | None
    answerable: bool
    context: str


class RagService:
    def __init__(self, retriever, reranker, llm: LLM, settings: Settings) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._llm = llm
        self._settings = settings

    def retrieve(self, question: str) -> tuple[list[Hit], float]:
        hits = self._retriever.search(question, top_k=self._settings.top_k_pre)
        hits = self._reranker.rerank(question, hits)
        hits = filter_by_threshold(hits, self._settings.min_sim, self._settings.top_k_post)
        relevance = round(
            max((self._retriever.similarity(question, h.chunk_id) for h in hits), default=0.0), 3
        )
        return hits, relevance

    def prepare(
        self, question: str, use_rag: bool = True, prompt_key: str = "baseline"
    ) -> Prepared:
        if not use_rag:
            return Prepared(build_messages([], "", question, "baseline"), [], None, True, "")
        hits, relevance = self.retrieve(question)
        if not hits or relevance < self._settings.no_answer_min_score:
            return Prepared([], hits, relevance, False, "")
        context = build_context(hits)
        return Prepared(
            build_messages([], context, question, prompt_key), hits, relevance, True, context
        )

    def finalize(
        self, text: str, prepared: Prepared, stats: GenerationStats | None = None
    ) -> RagAnswer:
        citations = tuple(extract_citations(text, prepared.hits)) if prepared.hits else ()
        return RagAnswer(
            reply=text,
            sources=tuple(prepared.hits),
            citations=citations,
            answerable=True,
            relevance=prepared.relevance,
            stats=stats,
        )

    async def answer(
        self, question: str, history: list[ChatMessage], use_rag: bool = True, profile=None, model=None
    ) -> RagAnswer:
        from app.application.optimization.profiles import get_profile

        profile = profile or get_profile("baseline")
        prepared = self.prepare(question, use_rag=use_rag, prompt_key=profile.prompt)
        if not prepared.answerable:
            return RagAnswer(reply=NO_ANSWER_TEXT, answerable=False, relevance=prepared.relevance)
        if use_rag:
            messages = build_messages(history, prepared.context, question, profile.prompt)
        else:
            messages = build_messages(history, "", question, "baseline")
            messages[0] = ChatMessage(messages[0].role, NO_RAG_SYSTEM)
        completion = await self._llm.complete(
            messages, think=profile.think, options=profile.options, model=model
        )
        return self.finalize(completion.text, prepared, completion.stats)
