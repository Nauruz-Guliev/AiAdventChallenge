from app.application.agent import RAGAgent
from app.application.evaluator import Evaluator, source_coverage
from app.domain.models import Hit, Question
from app.infrastructure.fake_llm import FakeLLM
from app.infrastructure.heuristic_reranker import HeuristicReranker


class StubRetriever:
    def search(self, question, top_k=4):
        return [Hit("c1", "docs/a.md", "A", "Intro", 0.9, "alpha")]


class NoopRewriter:
    async def rewrite(self, question):
        return question


def _agent():
    return RAGAgent(
        gateway=FakeLLM(answer="x"),
        retriever=StubRetriever(),
        reranker=HeuristicReranker(),
        rewriter=NoopRewriter(),
    )


async def test_evaluator_builds_report_with_all_modes():
    evaluator = Evaluator(agent=_agent(), gateway=FakeLLM(judge_score=1.0))
    questions = [Question("q1", "вопрос", "ожидание", ("a.md",))]
    report = await evaluator.evaluate(questions)
    assert len(report.items) == 1
    item = report.items[0]
    assert item.mode_scores["rag"] == 1.0
    assert item.source_coverage["rag"] is True
    assert item.source_coverage["no_rag"] is False
    assert report.summary["questions"] == 1
    assert set(report.summary["modes"]) == {
        "no_rag", "rag", "rag_filter", "rag_rewrite", "rag_full",
    }
    assert report.summary["modes"]["rag"]["avg_score"] == 1.0
    assert report.summary["modes"]["rag"]["source_coverage_rate"] == 1.0


def test_source_coverage_matches_substrings():
    hits = [Hit("c1", "docs/expect-actual.md", "A", "Intro", 0.9, "x")]
    assert source_coverage(("expect-actual",), hits) is True
    assert source_coverage(("ktor",), hits) is False
