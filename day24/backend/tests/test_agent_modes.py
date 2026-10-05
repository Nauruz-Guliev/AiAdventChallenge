from app.application.agent import RAGAgent
from app.domain.models import Hit
from app.infrastructure.fake_llm import FakeLLM
from app.infrastructure.heuristic_reranker import HeuristicReranker


class StubRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.queries = []

    def search(self, question, top_k=4):
        self.queries.append((question, top_k))
        return self.hits[:top_k]


class StubRewriter:
    def __init__(self, query="ktor client setup"):
        self.query = query
        self.calls = []

    async def rewrite(self, question):
        self.calls.append(question)
        return self.query


def _hits():
    return [
        Hit("c1", "docs/a.md", "A", "Intro", 0.9, "alpha ktor"),
        Hit("c2", "docs/b.md", "B", "Misc", 0.2, "beta unrelated"),
        Hit("c3", "docs/c.md", "C", "Client", 0.5, "ktor client usage"),
    ]


def _agent(hits=None, k_pre=30, k_post=8, min_sim=0.35, no_answer_min_score=0.0):
    agent = RAGAgent(
        gateway=FakeLLM(answer="alpha ktor [1]"),
        retriever=StubRetriever(hits if hits is not None else _hits()),
        reranker=HeuristicReranker(),
        rewriter=StubRewriter(),
        k_pre=k_pre, k_post=k_post, min_sim=min_sim,
        min_quote_len=3, no_answer_min_score=no_answer_min_score,
    )
    return agent


async def test_rag_uses_original_question_and_no_filter():
    agent = _agent()
    answer = await agent.answer("вопрос", mode="rag")
    assert answer.sources[0].chunk_id == "c1"
    assert len(answer.sources) == 3


async def test_rag_guard_rewrites_and_filters():
    agent = _agent()
    answer = await agent.answer("Как настроить Ktor?", mode="rag_guard")
    ids = [h.chunk_id for h in answer.sources]
    assert "c2" not in ids
    assert answer.relevance == 0.9
    assert len(answer.citations) >= 1


async def test_rag_guard_answers_not_know_when_below_threshold():
    agent = _agent(no_answer_min_score=0.99)
    answer = await agent.answer("Как настроить Ktor?", mode="rag_guard")
    assert answer.answerable is False
    assert "не нашёл" in answer.text
    assert answer.sources == ()
    assert answer.citations == ()


async def test_rag_guard_not_know_when_no_hits():
    agent = _agent(hits=[], no_answer_min_score=0.5)
    answer = await agent.answer("Как настроить Ktor?", mode="rag_guard")
    assert answer.answerable is False


async def test_rag_returns_citations_grounded():
    agent = _agent()
    answer = await agent.answer("вопрос", mode="rag")
    assert answer.citations[0].grounded is True
