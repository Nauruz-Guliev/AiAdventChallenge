from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Optional, Protocol

from app.domain.models import ChatMessage, GenerationStats


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


class LLMClient(Protocol):
    def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        options: Optional[dict] = None,
    ) -> AsyncIterator[StreamEvent]: ...

    async def list_models(self) -> list[ModelInfo]: ...

    async def health(self) -> bool: ...
