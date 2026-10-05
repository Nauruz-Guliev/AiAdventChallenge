from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    source: str
    title: str
    section: str
    score: float
    text: str


@dataclass(frozen=True)
class Answer:
    mode: Literal["no_rag", "rag"]
    text: str
    sources: tuple[Hit, ...]


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    expectation: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class EvalItem:
    question: str
    expectation: str
    sources: list[str]
    no_rag_answer: str
    no_rag_score: float
    rag_answer: str
    rag_score: float
    rag_sources: list[str]
    source_coverage: bool


@dataclass(frozen=True)
class EvalReport:
    items: list[EvalItem]
    summary: dict


class LLMGatewayError(RuntimeError):
    pass


class IndexNotFound(RuntimeError):
    pass


class InvalidQuestion(ValueError):
    pass
