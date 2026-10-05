from app.application.chat_service import ChatService
from app.application.scenario_runner import run_scenario
from app.domain.models import Hit
from app.infrastructure.fake_llm import FakeLLM
from app.infrastructure.heuristic_reranker import HeuristicReranker
from app.infrastructure.session_store import SessionStore


class StubRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, question, top_k=4):
        return self.hits[:top_k]

    def similarity(self, text, chunk_id):
        return next((h.score for h in self.hits if h.chunk_id == chunk_id), 0.0)


class StubRewriter:
    async def rewrite(self, question):
        return "kotlin multiplatform"


def _service():
    llm = FakeLLM(
        answer="настраиваем проект [1]",
        memory={
            "goal": "настроить KMP проект",
            "constraints": ["Kotlin 2.0"],
            "clarifications": ["targets"],
            "terms": [],
        },
    )
    hits = [Hit("c1", "docs/a.md", "A", "Intro", 0.9, "kotlin multiplatform setup")]
    return ChatService(
        gateway=llm,
        retriever=StubRetriever(hits),
        reranker=HeuristicReranker(),
        rewriter=StubRewriter(),
        min_quote_len=3,
        no_answer_min_score=0.0,
    )


async def test_scenario_passes(tmp_path):
    report = await run_scenario(
        _service(), SessionStore(tmp_path),
        name="test", goal="настроить KMP проект",
        messages=[
            {"role": "user", "text": "помоги настроить проект"},
            {"role": "user", "text": "нужны таргеты"},
        ],
    )
    assert report.passed is True
    assert report.all_with_sources is True
    assert report.goal_kept is True
    assert report.memory_grown is True
    assert report.turns == 4
