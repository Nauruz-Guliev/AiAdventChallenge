import json

import pytest

from app.application.optimization.ab_runner import ABRunner
from app.application.rag_service import Prepared
from app.config import Settings
from app.domain.models import ChatMessage, GenerationStats, Hit, ResourceSample, Role
from app.ports.llm import Completion, ModelInfo


class FakeLLM:
    def __init__(self, models=None):
        self._models = models or []

    async def complete(self, messages, think=False, options=None, model=None):
        return Completion(
            text="ok [1]",
            stats=GenerationStats(
                model=model or "gemma4:12b",
                prompt_tokens=100,
                completion_tokens=10,
                eval_duration_ns=1_000_000_000,
                load_duration_ns=500_000_000,
            ),
        )

    async def list_models(self):
        return [ModelInfo(name=n) for n in self._models]

    async def tags(self):
        return [{"name": "gemma4:12b", "size": 8_000_000_000}]

    async def ps(self):
        return [{"name": "gemma4:12b", "size_vram": 5_000_000_000}]


class FakeSampler:
    async def start(self):
        pass

    async def stop(self):
        pass

    def result(self):
        return ResourceSample(rss_peak_mb=1234.0, cpu_percent=55.0)


class FakeRag:
    def prepare(self, question, use_rag=True, prompt_key="baseline"):
        return Prepared(
            [ChatMessage(Role.USER, question)],
            [Hit("c0", "doc.md", "T", "S", 0.9, "x")],
            0.9,
            True,
            "ctx",
        )


class FakeJudge:
    async def score(self, question, expectation, answer):
        return 0.5


def _questions(tmp_path, n=3):
    p = tmp_path / "q.json"
    p.write_text(
        json.dumps([{"id": f"q{i}", "question": f"Q{i}?", "expectation": "E"} for i in range(n)]),
        encoding="utf-8",
    )
    return p


def _settings(tmp_path):
    return Settings(
        _env_file=None, telegram_bot_token="1:x", eval_questions_path=str(_questions(tmp_path))
    )


@pytest.mark.asyncio
async def test_quick_run_produces_cells_with_resources(tmp_path):
    runner = ABRunner(
        _settings(tmp_path),
        FakeRag(),
        FakeLLM(models=["gemma4:12b"]),
        FakeJudge(),
        sampler_factory=lambda: FakeSampler(),
    )
    rep = await runner.run(quick=True)
    assert rep.quick is True and rep.questions == 3 and rep.runs == 1
    assert {c.quant for c in rep.cells} == {"q4"}
    assert {c.profile for c in rep.cells} == {"baseline", "params", "optimized"}
    assert all(c.resources.rss_peak_mb == 1234.0 for c in rep.cells)
    assert rep.cells[0].quality_mean == 0.5


@pytest.mark.asyncio
async def test_q8_missing_is_noted(tmp_path):
    runner = ABRunner(
        _settings(tmp_path),
        FakeRag(),
        FakeLLM(models=["gemma4:12b"]),
        FakeJudge(),
        sampler_factory=lambda: FakeSampler(),
    )
    rep = await runner.run(quick=True)
    assert any("Q8_0" in n for n in rep.notes)


@pytest.mark.asyncio
async def test_errors_are_counted(tmp_path):
    class BoomLLM(FakeLLM):
        async def complete(self, messages, think=False, options=None, model=None):
            raise RuntimeError("boom")

    runner = ABRunner(
        _settings(tmp_path),
        FakeRag(),
        BoomLLM(models=["gemma4:12b"]),
        FakeJudge(),
        sampler_factory=lambda: FakeSampler(),
    )
    rep = await runner.run(quick=True)
    assert all(c.error_rate == 1.0 for c in rep.cells)
    assert all(c.quality_mean is None for c in rep.cells)
