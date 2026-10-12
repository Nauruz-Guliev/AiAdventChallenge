from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Awaitable, Callable

from app.application.rag_service import RagService
from app.config import Settings
from app.domain.models import EvalQuestion, EvalReport, EvalRow
from app.ports.judge import Judge
from app.ports.llm import LLM

ROWS = ("Локальная+RAG", "Облако+RAG", "Локальная без RAG")
NO_ANSWER_ANSWER = "(ассистент не нашёл ответа в базе)"
Progress = Callable[[int, int], "Awaitable[None] | None"]


def load_questions(path: str | Path) -> list[EvalQuestion]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        EvalQuestion(
            id=q["id"],
            question=q["question"],
            expectation=q.get("expectation", ""),
            sources=tuple(q.get("sources", [])),
        )
        for q in data
    ]


@dataclass
class _Sample:
    score: float | None
    latency_ms: float
    tps: float
    error: bool


class BenchmarkRunner:
    def __init__(
        self,
        settings: Settings,
        rag_service: RagService,
        local_llm: LLM,
        cloud_llm: LLM | None,
        judge: Judge | None,
        questions_path: str | Path | None = None,
    ) -> None:
        self._settings = settings
        self._rag = rag_service
        self._local = local_llm
        self._cloud = cloud_llm
        self._judge = judge
        self._questions_path = questions_path or settings.eval_questions_path
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def run(self, runs: int | None = None, on_progress: Progress | None = None) -> EvalReport:
        runs = runs or self._settings.eval_runs
        questions = load_questions(self._questions_path)
        rows: dict[str, list[_Sample]] = {label: [] for label in ROWS}
        total = len(questions) * runs
        done = 0
        self._running = True
        try:
            for question in questions:
                for _ in range(runs):
                    samples = await self._run_one(question)
                    for label, sample in samples.items():
                        rows[label].append(sample)
                    done += 1
                    if on_progress:
                        maybe = on_progress(done, total)
                        if maybe is not None:
                            await maybe
        finally:
            self._running = False
        return EvalReport(
            rows=tuple(self._aggregate(label, rows[label]) for label in ROWS),
            questions=len(questions),
            runs=runs,
        )

    async def _run_one(self, question: EvalQuestion) -> dict[str, _Sample]:
        prepared_rag = self._rag.prepare(question.question, use_rag=True)
        prepared_no = self._rag.prepare(question.question, use_rag=False)
        return {
            ROWS[0]: await self._generate(self._local, prepared_rag, question),
            ROWS[1]: await self._generate(self._cloud, prepared_rag, question),
            ROWS[2]: await self._generate(self._local, prepared_no, question),
        }

    async def _generate(self, llm, prepared, question: EvalQuestion) -> _Sample:
        if llm is None:
            return _Sample(score=None, latency_ms=0.0, tps=0.0, error=True)
        if not prepared.answerable:
            score = await self._score(question, NO_ANSWER_ANSWER)
            return _Sample(score=score, latency_ms=0.0, tps=0.0, error=False)
        start = time.perf_counter()
        try:
            completion = await llm.complete(prepared.messages)
        except Exception:  # noqa: BLE001
            return _Sample(score=None, latency_ms=0.0, tps=0.0, error=True)
        latency_ms = (time.perf_counter() - start) * 1000.0
        tps = completion.stats.tokens_per_second if completion.stats else 0.0
        score = await self._score(question, completion.text)
        return _Sample(score=score, latency_ms=latency_ms, tps=tps, error=False)

    async def _score(self, question: EvalQuestion, answer: str) -> float | None:
        if self._judge is None:
            return None
        try:
            return await self._judge.score(question.question, question.expectation, answer)
        except Exception:  # noqa: BLE001
            return None

    def _aggregate(self, label: str, samples: list[_Sample]) -> EvalRow:
        errors = [s for s in samples if s.error]
        total = len(samples) or 1
        scores = [s.score for s in samples if not s.error and s.score is not None]
        latencies = [s.latency_ms for s in samples if not s.error and s.latency_ms > 0]
        tps = [s.tps for s in samples if not s.error and s.tps > 0]
        return EvalRow(
            label=label,
            quality_mean=round(mean(scores), 3) if scores else 0.0,
            quality_std=round(pstdev(scores), 3) if len(scores) > 1 else 0.0,
            latency_mean_ms=round(mean(latencies), 1) if latencies else 0.0,
            latency_std_ms=round(pstdev(latencies), 1) if len(latencies) > 1 else 0.0,
            tokens_per_second=round(mean(tps), 1) if tps else 0.0,
            error_rate=round(len(errors) / total, 3),
            runs=len(samples),
        )
