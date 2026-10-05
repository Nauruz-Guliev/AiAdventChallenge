from typing import Protocol

from app.domain.models import Hit


class Retriever(Protocol):
    def search(self, question: str, top_k: int = 4) -> list[Hit]:
        ...

    def similarity(self, text: str, chunk_id: str) -> float:
        ...
