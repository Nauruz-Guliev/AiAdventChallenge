import json
from functools import lru_cache
from pathlib import Path

from app.application.agent import RAGAgent
from app.application.evaluator import Evaluator
from app.domain.models import Question
from app.infrastructure.deepseek_gateway import DeepSeekGateway
from app.infrastructure.embeddings import get_embedder
from app.infrastructure.fake_llm import FakeLLM
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
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )


@lru_cache
def get_retriever() -> JsonRetriever:
    settings = get_settings()
    return JsonRetriever(
        index_path=Path(settings.index_path),
        embedder=get_embedder("sentence"),
        top_k=settings.top_k,
    )


def get_agent() -> RAGAgent:
    settings = get_settings()
    return RAGAgent(gateway=get_llm(), retriever=get_retriever(), top_k=settings.top_k)


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
