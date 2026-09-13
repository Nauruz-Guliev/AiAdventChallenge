from typing import Protocol

from app.domain.models import ChatMessage, LLMResponse


class LLMGateway(Protocol):
    async def complete(self, messages: list[ChatMessage]) -> LLMResponse:
        ...
