from typing import Protocol

from app.domain.invariant import Invariant


class InvariantRepository(Protocol):
    async def list(self) -> list[Invariant]:
        ...

    async def add(self, text: str, category: str) -> Invariant:
        ...

    async def remove(self, invariant_id: str) -> None:
        ...
