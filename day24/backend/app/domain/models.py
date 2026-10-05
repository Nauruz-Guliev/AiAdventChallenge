from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Mode = Literal["no_rag", "rag", "rag_guard"]


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    source: str
    title: str
    section: str
    score: float
    text: str


@dataclass(frozen=True)
class Citation:
    ref: int
    chunk_id: str
    source: str
    section: str
    quote: str
    grounded: bool


@dataclass(frozen=True)
class Answer:
    mode: Mode
    text: str
    sources: tuple[Hit, ...]
    citations: tuple[Citation, ...] = ()
    answerable: bool = True
    relevance: float | None = None


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
    mode_citations: dict[str, list[dict]]
    has_citations: dict[str, bool]
    grounding_rate: dict[str, float]
    support_scores: dict[str, float]
    no_answer: dict[str, bool]


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
