from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Mode = Literal["no_rag", "rag", "rag_filter", "rag_rewrite", "rag_full"]


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
    mode: Mode
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
    mode_answers: dict[str, str]
    mode_scores: dict[str, float]
    mode_sources: dict[str, list[str]]
    source_coverage: dict[str, bool]


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
