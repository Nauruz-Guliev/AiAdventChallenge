from __future__ import annotations

import json
import re

from app.application.agent import RAGAgent
from app.domain.models import EvalItem, EvalReport, Hit, Question
from app.ports.llm_gateway import LLMGateway

DEFAULT_MODES = ["no_rag", "rag", "rag_filter", "rag_rewrite", "rag_full"]

JUDGE_SYSTEM = (
    "JUDGE Ты оцениваешь качество ответа на вопрос по ожиданию. "
    'Верни ТОЛЬКО JSON: {"score": <число от 0 до 1>}.'
)


def source_coverage(expected: tuple[str, ...], hits: list[Hit]) -> bool:
    if not expected:
        return False
    haystack = " ".join(f"{h.source} {h.section}".lower() for h in hits)
    return all(exp.lower() in haystack for exp in expected)


def _parse_score(reply: str) -> float:
    try:
        return float(json.loads(reply).get("score", 0.0))
    except (ValueError, TypeError):
        match = re.search(r'"score"\s*:\s*([0-9.]+)', reply)
        if match:
            return float(match.group(1))
        return 0.0


class Evaluator:
    def __init__(self, agent: RAGAgent, gateway: LLMGateway, modes: list[str] | None = None):
        self._agent = agent
        self._gateway = gateway
        self._modes = list(modes or DEFAULT_MODES)

    async def judge(self, expectation: str, answer: str) -> float:
        reply = await self._gateway.complete([
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": f"Ожидание: {expectation}\nОтвет: {answer}"},
        ])
        return _parse_score(reply)

    async def evaluate(self, questions: list[Question]) -> EvalReport:
        items: list[EvalItem] = []
        for q in questions:
            mode_answers: dict[str, str] = {}
            mode_scores: dict[str, float] = {}
            mode_sources: dict[str, list[str]] = {}
            coverage: dict[str, bool] = {}
            for mode in self._modes:
                answer = await self._agent.answer(q.question, mode=mode)
                score = await self.judge(q.expectation, answer.text)
                mode_answers[mode] = answer.text
                mode_scores[mode] = round(score, 3)
                mode_sources[mode] = [f"{h.source} :: {h.section}" for h in answer.sources]
                coverage[mode] = source_coverage(q.sources, list(answer.sources))
            items.append(EvalItem(
                question=q.question,
                expectation=q.expectation,
                sources=list(q.sources),
                mode_answers=mode_answers,
                mode_scores=mode_scores,
                mode_sources=mode_sources,
                source_coverage=coverage,
            ))
        return EvalReport(items=items, summary=self._summary(items))

    def _summary(self, items: list[EvalItem]) -> dict:
        n = len(items) or 1
        modes: dict[str, dict] = {}
        for mode in self._modes:
            avg = sum(i.mode_scores.get(mode, 0.0) for i in items) / n
            covered = sum(1 for i in items if i.source_coverage.get(mode))
            modes[mode] = {
                "avg_score": round(avg, 3),
                "source_coverage_rate": round(covered / n, 3),
            }
        return {"questions": len(items), "modes": modes}
