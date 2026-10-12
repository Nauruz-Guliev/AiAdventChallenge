from __future__ import annotations

from typing import AsyncIterator, Optional

import pytest

from app.domain.models import ChatMessage, GenerationStats
from app.ports.llm import ModelInfo, OllamaUnavailable, StreamDelta, StreamDone


class FakeLLMClient:
    def __init__(self, deltas=None, stats=None, models=None, fail=False):
        self._deltas = deltas if deltas is not None else ["Hel", "lo"]
        self._stats = stats or GenerationStats(
            model="gemma4:12b", prompt_tokens=5, completion_tokens=2,
            eval_duration_ns=1_000_000_000, total_duration_ns=2_000_000_000,
        )
        self._models = models or [ModelInfo(name="gemma4:12b", parameter_size="11.9B")]
        self._fail = fail
        self.calls: list[list[ChatMessage]] = []

    async def stream_chat(self, messages, model, options=None) -> AsyncIterator:
        self.calls.append(list(messages))
        if self._fail:
            raise OllamaUnavailable("boom")
        for d in self._deltas:
            yield StreamDelta(kind="content", text=d)
        yield StreamDone(stats=self._stats)

    async def list_models(self):
        return list(self._models)

    async def health(self) -> bool:
        return not self._fail


@pytest.fixture
def fake_llm():
    return FakeLLMClient()


@pytest.fixture
def settings():
    from app.config import Settings
    return Settings(
        _env_file=None, telegram_bot_token="42:ABC",
        history_max_messages=4, history_max_chars=1000,
    )
