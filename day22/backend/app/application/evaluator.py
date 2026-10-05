from __future__ import annotations

import json
import re

from app.application.agent import RAGAgent
from app.domain.models import EvalItem, EvalReport, Hit, Question
from app.ports.llm_gateway import LLMGateway

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
    def __init__(self, agent: RAGAgent, gateway: LLMGateway):
        self._agent = agent
        self._gateway = gateway

    async def judge(self, expectation: str, answer: str) -> float:
        reply = await self._gateway.complete([
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": f"Ожидание: {expectation}\nОтвет: {answer}"},
        ])
        return _parse_score(reply)

    async def evaluate(self, questions: list[Question]) -> EvalReport:
        items: list[EvalItem] = []
        for q in questions:
            no_rag = await self._agent.answer(q.question, mode="no_rag")
            rag = await self._agent.answer(q.question, mode="rag")
            no_rag_score = await self.judge(q.expectation, no_rag.text)
            rag_score = await self.judge(q.expectation, rag.text)
            rag_sources = [f"{h.source} :: {h.section}" for h in rag.sources]
            items.append(EvalItem(
                question=q.question,
                expectation=q.expectation,
                sources=list(q.sources),
                no_rag_answer=no_rag.text,
                no_rag_score=round(no_rag_score, 3),
                rag_answer=rag.text,
                rag_score=round(rag_score, 3),
                rag_sources=rag_sources,
                source_coverage=source_coverage(q.sources, list(rag.sources)),
            ))
        return EvalReport(items=items, summary=self._summary(items))

    @staticmethod
    def _summary(items: list[EvalItem]) -> dict:
        n = len(items) or 1
        avg_no = sum(i.no_rag_score for i in items) / n
        avg_rag = sum(i.rag_score for i in items) / n
        covered = sum(1 for i in items if i.source_coverage)
        return {
            "questions": len(items),
            "avg_no_rag_score": round(avg_no, 3),
            "avg_rag_score": round(avg_rag, 3),
            "source_coverage_rate": round(covered / n, 3),
        }
