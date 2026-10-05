from typing import Protocol

from app.domain.models import Hit


class Reranker(Protocol):
    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        ...
