from __future__ import annotations

import time
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Awaitable, Callable

from app.application.benchmark import load_questions
from app.application.optimization import profiles as prof
from app.application.prompt import build_messages
from app.application.rag_service import RagService
from app.config import Settings
from app.domain.models import ABReport, CellResult, EvalQuestion, ResourceSample
from app.infrastructure import resources as res
from app.ports.judge import Judge
from app.ports.llm import LLM

Progress = Callable[[int, int], "Awaitable[None] | None"]
NO_ANSWER_ANSWER = "(ассистент не нашёл ответа в базе)"
APPROX_CHARS_PER_TOKEN = 3.2


@dataclass
class _Sample:
    score: float | None
    latency_ms: float
    tps: float
    prompt_tokens: int
    load_ms: float
    bumped: bool
    error: bool


class ABRunner:
    def __init__(
        self,
        settings: Settings,
        rag_service: RagService,
        local_llm: LLM,
        judge: Judge | None = None,
        sampler_factory=None,
    ) -> None:
        self._s = settings
        self._rag = rag_service
        self._llm = local_llm
        self._judge = judge
        self._sampler_factory = sampler_factory or (
            lambda: res.ResourceSampler(settings.resource_sample_interval)
        )
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def run(self, quick: bool = True, on_progress: Progress | None = None) -> ABReport:
        n = self._s.ab_quick_questions if quick else self._s.ab_full_questions
        runs = 1 if quick else self._s.ab_runs
        questions = load_questions(self._s.eval_questions_path)[:n]
        profiles = [prof.get_profile(p) for p in prof.PROFILE_ORDER]
        available = [prof.get_quant(q) for q in prof.QUANT_ORDER]
        notes: list[str] = []

        try:
            names = {m.name for m in await self._llm.list_models()}
        except Exception:  # noqa: BLE001
            names = set()
        if names:
            ready = [q for q in available if q.model in names]
            for q in available:
                if q.model not in names:
                    notes.append(f"{q.label} ({q.model}) не установлен — пропущен")
            available = ready
        if not available:
            notes.append("Ни одна модель не найдена — прогон невозможен")
            return ABReport((), len(questions), runs, quick, tuple(notes))

        preps = {
            q.id: {p.name: self._rag.prepare(q.question, use_rag=True, prompt_key=p.prompt) for p in profiles}
            for q in questions
        }
        total = len(questions) * runs * len(profiles) * len(available)
        done = 0
        cells: list[CellResult] = []
        self._running = True
        try:
            for quant in available:
                size_gb = await self._model_size(quant.model)
                sampler = self._sampler_factory()
                await sampler.start()
                for profile in profiles:
                    samples: list[_Sample] = []
                    first_load = 0.0
                    for q in questions:
                        prep = preps[q.id][profile.name]
                        for _ in range(runs):
                            s = await self._generate(profile, quant, prep, q)
                            if s.load_ms and not first_load:
                                first_load = s.load_ms
                            samples.append(s)
                            done += 1
                            if on_progress:
                                maybe = on_progress(done, total)
                                if maybe is not None:
                                    await maybe
                    await sampler.stop()
                    base = sampler.result()
                    vram = await self._vram(quant.model)
                    resources = ResourceSample(
                        model_size_gb=size_gb,
                        size_vram_gb=vram,
                        rss_peak_mb=base.rss_peak_mb,
                        cpu_percent=base.cpu_percent,
                        load_ms=first_load,
                    )
                    cells.append(self._cell(profile, quant, samples, resources))
        finally:
            self._running = False
        return ABReport(tuple(cells), len(questions), runs, quick, tuple(notes))

    def _options(self, profile, prep, question: str) -> tuple[dict, bool]:
        opts = dict(profile.options)
        bumped = False
        approx = (len(prep.context) + len(question)) / APPROX_CHARS_PER_TOKEN
        if "num_ctx" in opts and approx + float(opts.get("num_predict", 0)) > float(opts["num_ctx"]):
            opts["num_ctx"] = 6144
            bumped = True
        return opts, bumped

    async def _generate(self, profile, quant, prep, question: EvalQuestion) -> _Sample:
        if not prep.answerable:
            score = await self._score(question, NO_ANSWER_ANSWER)
            return _Sample(score, 0.0, 0.0, 0, 0.0, False, False)
        opts, bumped = self._options(profile, prep, question.question)
        messages = build_messages([], prep.context, question.question, profile.prompt)
        t0 = time.perf_counter()
        try:
            comp = await self._llm.complete(
                messages, think=profile.think, options=opts, model=quant.model
            )
        except Exception:  # noqa: BLE001
            return _Sample(None, 0.0, 0.0, 0, 0.0, bumped, True)
        latency = (time.perf_counter() - t0) * 1000.0
        st = comp.stats
        return _Sample(
            score=await self._score(question, comp.text),
            latency_ms=latency,
            tps=st.tokens_per_second if st else 0.0,
            prompt_tokens=st.prompt_tokens if st else 0,
            load_ms=(st.load_duration_ns / 1e6) if st else 0.0,
            bumped=bumped,
            error=False,
        )

    async def _score(self, question: EvalQuestion, answer: str) -> float | None:
        if self._judge is None:
            return None
        try:
            return await self._judge.score(question.question, question.expectation, answer)
        except Exception:  # noqa: BLE001
            return None

    async def _model_size(self, model: str) -> float:
        try:
            return await res.model_size_gb(self._llm, model)
        except Exception:  # noqa: BLE001
            return 0.0

    async def _vram(self, model: str) -> float:
        try:
            return await res.size_vram_gb(self._llm, model)
        except Exception:  # noqa: BLE001
            return 0.0

    def _cell(self, profile, quant, samples: list[_Sample], resources: ResourceSample) -> CellResult:
        scores = [s.score for s in samples if not s.error and s.score is not None]
        lats = [s.latency_ms for s in samples if not s.error and s.latency_ms > 0]
        tps = [s.tps for s in samples if not s.error and s.tps > 0]
        pts = [s.prompt_tokens for s in samples if not s.error and s.prompt_tokens > 0]
        errors = [s for s in samples if s.error]
        total = len(samples) or 1
        return CellResult(
            profile=profile.name,
            quant=quant.name,
            label=f"{profile.label} · {quant.label}",
            quality_mean=round(mean(scores), 3) if scores else None,
            quality_std=round(pstdev(scores), 3) if len(scores) > 1 else (0.0 if scores else None),
            latency_mean_ms=round(mean(lats), 1) if lats else 0.0,
            latency_std_ms=round(pstdev(lats), 1) if len(lats) > 1 else 0.0,
            tokens_per_second=round(mean(tps), 1) if tps else 0.0,
            prompt_tokens=round(mean(pts), 0) if pts else 0.0,
            error_rate=round(len(errors) / total, 3),
            runs=len(samples),
            ctx_bumped=any(s.bumped for s in samples),
            resources=resources,
        )
