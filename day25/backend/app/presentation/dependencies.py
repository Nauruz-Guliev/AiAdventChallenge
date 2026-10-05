from functools import lru_cache
from pathlib import Path

from app.application.chat_service import ChatService
from app.application.scenario_runner import run_all_scenarios
from app.infrastructure.deepseek_gateway import DeepSeekGateway
from app.infrastructure.embeddings import get_embedder
from app.infrastructure.fake_llm import FakeLLM
from app.infrastructure.heuristic_reranker import HeuristicReranker
from app.infrastructure.retrieval import JsonRetriever
from app.infrastructure.session_store import SessionStore
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


def get_rewriter():
    from app.application.query_rewriter import QueryRewriter

    settings = get_settings()
    return QueryRewriter(gateway=get_llm(), enabled=settings.rewrite_enabled)


@lru_cache
def get_store() -> SessionStore:
    settings = get_settings()
    return SessionStore(settings.sessions_dir)


def get_chat_service() -> ChatService:
    settings = get_settings()
    return ChatService(
        gateway=get_llm(),
        retriever=get_retriever(),
        reranker=get_reranker(),
        rewriter=get_rewriter(),
        k_pre=settings.k_pre,
        k_post=settings.k_post,
        min_sim=settings.min_sim,
        min_quote_len=settings.min_quote_len,
        no_answer_min_score=settings.no_answer_min_score,
    )


async def run_scenarios():
    settings = get_settings()
    return await run_all_scenarios(get_chat_service(), get_store(), settings.scenarios_dir)
