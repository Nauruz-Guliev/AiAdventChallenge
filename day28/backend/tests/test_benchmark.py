import json

import pytest

from app.application.benchmark import BenchmarkRunner
from app.application.rag_service import Prepared
from app.config import Settings
from app.domain.models import ChatMessage, CloudUnavailable, Hit, RagAnswer, Role
from app.ports.llm import Completion


class FakeRagService:
    def __init__(self, answerable=True):
        self._answerable = answerable

    def prepare(self, question, use_rag=True):
        hits = [Hit("c0", "doc.md", "T", "S", 0.9, "text")] if use_rag else []
        return Prepared([ChatMessage(Role.USER, question)], hits, 0.9, self._answerable, "ctx")

    def finalize(self, text, prepared, stats=None):
        return RagAnswer(reply=text, sources=tuple(prepared.hits), answerable=True, stats=stats)


class FakeLLM:
    def __init__(self, text="ans"):
        self._text = text

    async def complete(self, messages, think=False):
        return Completion(text=self._text)


class FakeJudge:
    def __init__(self, score=0.5):
        self._score = score

    async def score(self, question, expectation, answer):
        return self._score


def _write_questions(tmp_path):
    p = tmp_path / "q.json"
    p.write_text(json.dumps([
        {"id": "q1", "question": "Q1?", "expectation": "E1", "sources": []},
        {"id": "q2", "question": "Q2?", "expectation": "E2", "sources": []},
    ]), encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_benchmark_aggregates(tmp_path):
    s = Settings(_env_file=None, telegram_bot_token="1:x")
    runner = BenchmarkRunner(s, FakeRagService(), FakeLLM(), FakeLLM(), FakeJudge(0.6),
                             questions_path=_write_questions(tmp_path))
    report = await runner.run(runs=1)
    assert report.questions == 2 and report.runs == 1
    assert len(report.rows) == 3
    assert report.rows[0].quality_mean == 0.6


@pytest.mark.asyncio
async def test_benchmark_counts_errors(tmp_path):
    class BoomLLM:
        async def complete(self, messages, think=False):
            raise CloudUnavailable("boom")

    s = Settings(_env_file=None, telegram_bot_token="1:x")
    runner = BenchmarkRunner(s, FakeRagService(), BoomLLM(), BoomLLM(), FakeJudge(0.6),
                             questions_path=_write_questions(tmp_path))
    report = await runner.run(runs=1)
    assert report.rows[0].error_rate == 1.0
