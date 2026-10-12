from __future__ import annotations

from typing import AsyncIterator, Protocol

from app.domain.models import (
    ChatMessage,
    Completion,
    ModelInfo,
    StreamDelta,
    StreamDone,
)


class LlmGateway(Protocol):
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        num_ctx: int | None = None,
    ) -> Completion: ...

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        num_ctx: int | None = None,
    ) -> AsyncIterator[StreamDelta | StreamDone]: ...

    async def list_models(self) -> list[ModelInfo]: ...

    async def health(self) -> bool: ...

    async def loaded_models(self) -> list[dict]: ...
