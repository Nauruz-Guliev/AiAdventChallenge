from __future__ import annotations

import json
import re

from app.application.agent import RAGAgent
from app.domain.models import EvalItem, EvalReport, Hit, Question
from app.ports.llm_gateway import LLMGateway

DEFAULT_MODES = ["no_rag", "rag", "rag_guard"]

JUDGE_SYSTEM = (
    "JUDGE Ты оцениваешь качество ответа на вопрос по ожиданию. "
    'Верни ТОЛЬКО JSON: {"score": <число от 0 до 1>}.'
)

SUPPORT_SYSTEM = (
    "JUDGE Ты оцениваешь, подтверждается ли ответ приведёнными цитатами. "
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


def _citation_dicts(citations) -> list[dict]:
    return [
        {
            "ref": c.ref, "chunk_id": c.chunk_id, "source": c.source,
            "section": c.section, "quote": c.quote, "grounded": c.grounded,
        }
        for c in citations
    ]


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

    async def judge_support(self, question: str, answer: str, citations) -> float:
        quotes = "\n".join(
            f"[{c.ref}] {c.source} :: {c.section}: {c.quote}" for c in citations
        ) or "(нет цитат)"
        reply = await self._gateway.complete([
            {"role": "system", "content": SUPPORT_SYSTEM},
            {"role": "user", "content": f"Вопрос: {question}\nОтвет: {answer}\nЦитаты:\n{quotes}"},
        ])
        return _parse_score(reply)

    async def evaluate(self, questions: list[Question]) -> EvalReport:
        items: list[EvalItem] = []
        for q in questions:
            mode_answers, mode_scores, mode_sources = {}, {}, {}
            coverage, mode_citations, has_citations = {}, {}, {}
            grounding_rate, support_scores, no_answer = {}, {}, {}
            for mode in self._modes:
                answer = await self._agent.answer(q.question, mode=mode)
                score = await self.judge(q.expectation, answer.text)
                citations = list(answer.citations)
                grounded = [c for c in citations if c.grounded]
                gr = (len(grounded) / len(citations)) if citations else 0.0
                support = await self.judge_support(q.question, answer.text, citations)
                mode_answers[mode] = answer.text
                mode_scores[mode] = round(score, 3)
                mode_sources[mode] = [f"{h.source} :: {h.section}" for h in answer.sources]
                coverage[mode] = source_coverage(q.sources, list(answer.sources))
                mode_citations[mode] = _citation_dicts(citations)
                has_citations[mode] = len(grounded) > 0
                grounding_rate[mode] = round(gr, 3)
                support_scores[mode] = round(support, 3)
                no_answer[mode] = not answer.answerable
            items.append(EvalItem(
                question=q.question, expectation=q.expectation, sources=list(q.sources),
                mode_answers=mode_answers, mode_scores=mode_scores, mode_sources=mode_sources,
                source_coverage=coverage, mode_citations=mode_citations,
                has_citations=has_citations, grounding_rate=grounding_rate,
                support_scores=support_scores, no_answer=no_answer,
            ))
        return EvalReport(items=items, summary=self._summary(items))

    def _summary(self, items: list[EvalItem]) -> dict:
        n = len(items) or 1
        modes: dict[str, dict] = {}
        for mode in self._modes:
            avg = sum(i.mode_scores.get(mode, 0.0) for i in items) / n
            covered = sum(1 for i in items if i.source_coverage.get(mode))
            cited = sum(1 for i in items if i.has_citations.get(mode))
            avg_grounding = sum(i.grounding_rate.get(mode, 0.0) for i in items) / n
            avg_support = sum(i.support_scores.get(mode, 0.0) for i in items) / n
            no_ans = sum(1 for i in items if i.no_answer.get(mode))
            modes[mode] = {
                "avg_score": round(avg, 3),
                "source_coverage_rate": round(covered / n, 3),
                "citation_rate": round(cited / n, 3),
                "avg_grounding": round(avg_grounding, 3),
                "avg_support": round(avg_support, 3),
                "no_answer_rate": round(no_ans / n, 3),
            }
        return {"questions": len(items), "modes": modes}
