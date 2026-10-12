from __future__ import annotations

from typing import AsyncIterator

from app.application.context import check_budget, clamp_max_tokens
from app.domain.models import (
    ChatMessage,
    Completion,
    InvalidRequest,
    ModelInfo,
    StreamDelta,
    StreamDone,
)
from app.ports.llm import LlmGateway

_ALLOWED_ROLES = {"system", "user", "assistant"}


class ChatService:
    def __init__(
        self,
        gateway: LlmGateway,
        *,
        default_model: str,
        num_ctx: int,
        max_tokens_default: int,
        max_tokens_limit: int,
    ) -> None:
        self._gateway = gateway
        self._default_model = default_model
        self._num_ctx = num_ctx
        self._max_tokens_default = max_tokens_default
        self._max_tokens_limit = max_tokens_limit

    def _prepare(
        self, messages: list[ChatMessage], model: str | None, max_tokens: int | None
    ) -> tuple[str, int]:
        if not messages:
            raise InvalidRequest("messages не может быть пустым")
        for message in messages:
            if message.role not in _ALLOWED_ROLES:
                raise InvalidRequest(f"Недопустимая роль: {message.role}")
        limit = clamp_max_tokens(max_tokens, self._max_tokens_default, self._max_tokens_limit)
        check_budget(messages, limit, self._num_ctx)
        return model or self._default_model, limit

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Completion:
        chosen, limit = self._prepare(messages, model, max_tokens)
        return await self._gateway.chat(
            messages,
            model=chosen,
            temperature=temperature,
            max_tokens=limit,
            num_ctx=self._num_ctx,
        )

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamDelta | StreamDone]:
        chosen, limit = self._prepare(messages, model, max_tokens)

        async def generator() -> AsyncIterator[StreamDelta | StreamDone]:
            async for event in self._gateway.stream(
                messages,
                model=chosen,
                temperature=temperature,
                max_tokens=limit,
                num_ctx=self._num_ctx,
            ):
                yield event

        return generator()

    async def list_models(self) -> list[ModelInfo]:
        return await self._gateway.list_models()

    async def health(self) -> bool:
        return await self._gateway.health()
