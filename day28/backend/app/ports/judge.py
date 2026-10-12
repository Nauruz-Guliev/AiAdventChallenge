from typing import Protocol


class Judge(Protocol):
    async def score(self, question: str, expectation: str, answer: str) -> float: ...
