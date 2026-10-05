from app.application.agent import RAGAgent
from app.application.evaluator import Evaluator, source_coverage
from app.domain.models import Hit, Question
from app.infrastructure.fake_llm import FakeLLM


class StubRetriever:
    def search(self, question, top_k=4):
        return [Hit("c1", "docs/a.md", "A", "Intro", 0.9, "alpha")]


async def test_evaluator_builds_report_and_summary():
    agent = RAGAgent(gateway=FakeLLM(answer="x"), retriever=StubRetriever())
    evaluator = Evaluator(agent=agent, gateway=FakeLLM(judge_score=1.0))
    questions = [Question("q1", "вопрос", "ожидание", ("a.md",))]
    report = await evaluator.evaluate(questions)
    assert len(report.items) == 1
    item = report.items[0]
    assert item.no_rag_score == 1.0
    assert item.rag_score == 1.0
    assert item.source_coverage is True
    assert report.summary["questions"] == 1
    assert report.summary["avg_rag_score"] == 1.0
    assert report.summary["source_coverage_rate"] == 1.0


def test_source_coverage_matches_substrings():
    hits = [Hit("c1", "docs/expect-actual.md", "A", "Intro", 0.9, "x")]
    assert source_coverage(("expect-actual",), hits) is True
    assert source_coverage(("ktor",), hits) is False
