from __future__ import annotations

from app.config import Settings


class FakeRetriever:
    def __init__(self, hits=None, sim=0.9):
        from app.domain.models import Hit

        self._hits = hits or [Hit("c0", "doc.md", "T", "S", 0.9, "Kotlin Multiplatform.")]
        self._sim = sim

    def search(self, question, top_k=None):
        return list(self._hits)

    def similarity(self, text, chunk_id):
        return self._sim

    def chunk_count(self):
        return len(self._hits)


class FakeLocalLLM:
    def __init__(self, text="Ответ [1]", fail=False):
        self._text = text
        self._fail = fail

    async def complete(self, messages, think=False):
        from app.domain.models import GenerationStats, OllamaUnavailable
        from app.ports.llm import Completion

        if self._fail:
            raise OllamaUnavailable("boom")
        return Completion(
            text=self._text,
            stats=GenerationStats(
                model="gemma4:12b", completion_tokens=10, eval_duration_ns=1_000_000_000
            ),
        )

    async def stream_chat(self, messages, think=False, options=None):
        from app.domain.models import GenerationStats
        from app.ports.llm import StreamDelta, StreamDone

        for ch in self._text:
            yield StreamDelta(kind="content", text=ch)
        yield StreamDone(
            stats=GenerationStats(
                model="gemma4:12b", completion_tokens=10, eval_duration_ns=1_000_000_000
            )
        )

    async def list_models(self):
        return []

    async def health(self):
        return not self._fail


class FakeCloudLLM:
    def __init__(self, text="Облачный ответ"):
        self._text = text

    async def complete(self, messages, think=False):
        from app.ports.llm import Completion

        return Completion(text=self._text)


class FakeJudge:
    async def score(self, question, expectation, answer):
        return 0.5


def make_settings(**kw):
    return Settings(_env_file=None, telegram_bot_token="42:ABC", history_max_messages=4,
                    history_max_chars=1000, **kw)
