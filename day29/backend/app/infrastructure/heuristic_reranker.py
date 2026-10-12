from __future__ import annotations

import re

from app.domain.models import Hit

_TERM = re.compile(r"[a-zA-Zа-яА-Я0-9]+")


def tokenize(text: str) -> set[str]:
    return {
        t
        for t in (m.group(0).lower() for m in _TERM.finditer(text or ""))
        if len(t) >= 3
    }


def _overlap(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    return len(query_terms & tokenize(text)) / len(query_terms)


class HeuristicReranker:
    def __init__(self, w_sim: float = 0.6, w_lex: float = 0.3, w_head: float = 0.1):
        self.w_sim = w_sim
        self.w_lex = w_lex
        self.w_head = w_head

    def score(self, query: str, hit: Hit) -> float:
        terms = tokenize(query)
        lex = _overlap(terms, hit.text)
        head = 1.0 if terms & tokenize(f"{hit.title} {hit.section}") else 0.0
        return self.w_sim * hit.score + self.w_lex * lex + self.w_head * head

    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        return sorted(hits, key=lambda h: self.score(query, h), reverse=True)


def filter_by_threshold(hits: list[Hit], min_sim: float, k_post: int) -> list[Hit]:
    kept = [h for h in hits if h.score >= min_sim]
    if not kept:
        kept = hits
    return kept[:k_post]
