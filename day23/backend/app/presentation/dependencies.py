import json
from functools import lru_cache
from pathlib import Path

from app.application.agent import RAGAgent
from app.application.evaluator import Evaluator
from app.application.query_rewriter import QueryRewriter
from app.domain.models import Question
from app.infrastructure.deepseek_gateway import DeepSeekGateway
from app.infrastructure.embeddings import get_embedder
from app.infrastructure.fake_llm import FakeLLM
from app.infrastructure.heuristic_reranker import HeuristicReranker
from app.infrastructure.retrieval import JsonRetriever
from app.infrastructure.settings import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_llm():
    settings = get_settings()
    if settings.llm_provider == "fake":
        return FakeLLM()
    return DeepSeekGateway(
        settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )


@lru_cache
def get_retriever() -> JsonRetriever:
    settings = get_settings()
    return JsonRetriever(
        index_path=Path(settings.index_path),
        embedder=get_embedder("sentence"),
        top_k=settings.k_pre,
    )


@lru_cache
def get_reranker() -> HeuristicReranker:
    settings = get_settings()
    return HeuristicReranker(
        w_sim=settings.w_sim, w_lex=settings.w_lex, w_head=settings.w_head
    )


@lru_cache
def get_rewriter() -> QueryRewriter:
    settings = get_settings()
    return QueryRewriter(gateway=get_llm(), enabled=settings.rewrite_enabled)


def get_agent() -> RAGAgent:
    settings = get_settings()
    return RAGAgent(
        gateway=get_llm(),
        retriever=get_retriever(),
        reranker=get_reranker(),
        rewriter=get_rewriter(),
        k_pre=settings.k_pre,
        k_post=settings.k_post,
        min_sim=settings.min_sim,
    )


def get_evaluator() -> Evaluator:
    return Evaluator(agent=get_agent(), gateway=get_llm())


def get_questions() -> list[Question]:
    settings = get_settings()
    raw = json.loads(Path(settings.eval_questions_path).read_text(encoding="utf-8"))
    return [
        Question(
            id=q["id"],
            question=q["question"],
            expectation=q["expectation"],
            sources=tuple(q["sources"]),
        )
        for q in raw
    ]
