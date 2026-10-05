from typing import Protocol


class Rewriter(Protocol):
    async def rewrite(self, question: str) -> str:
        ...
