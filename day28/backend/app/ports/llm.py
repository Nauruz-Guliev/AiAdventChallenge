from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Optional, Protocol

from app.domain.models import ChatMessage, GenerationStats


@dataclass
class Completion:
    text: str
    stats: GenerationStats | None = None


@dataclass
class StreamDelta:
    kind: str  # "thinking" | "content"
    text: str


@dataclass
class StreamDone:
    stats: GenerationStats


StreamEvent = StreamDelta | StreamDone


@dataclass
class ModelInfo:
    name: str
    parameter_size: str = ""


class OllamaUnavailable(Exception):
    """Локальная модель недоступна или вернула ошибку."""


class LLM(Protocol):
    async def complete(self, messages: list[ChatMessage]) -> Completion: ...


class StreamingLLM(Protocol):
    def stream_chat(
        self, messages: list[ChatMessage], think: bool = False, options: Optional[dict] = None
    ) -> AsyncIterator[StreamEvent]: ...

    async def list_models(self) -> list[ModelInfo]: ...

    async def health(self) -> bool: ...
