from typing import Protocol


class LLMGateway(Protocol):
    async def complete(self, messages: list[dict[str, str]]) -> str:
        ...
