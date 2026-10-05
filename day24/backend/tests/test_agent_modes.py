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


def _agent(hits=None, k_pre=30, k_post=8, min_sim=0.35):
    retriever = StubRetriever(hits if hits is not None else _hits())
    rewriter = StubRewriter()
    agent = RAGAgent(
        gateway=FakeLLM(answer="x"),
        retriever=retriever,
        reranker=HeuristicReranker(),
        rewriter=rewriter,
        k_pre=k_pre,
        k_post=k_post,
        min_sim=min_sim,
    )
    return agent, retriever, rewriter


async def test_no_rag_has_no_sources():
    agent, _, _ = _agent()
    answer = await agent.answer("вопрос", mode="no_rag")
    assert answer.sources == ()


async def test_rag_uses_original_question_and_no_filter():
    agent, retriever, rewriter = _agent()
    answer = await agent.answer("вопрос", mode="rag")
    assert retriever.queries[0][0] == "вопрос"
    assert retriever.queries[0][1] == 8
    assert len(answer.sources) == 3
    assert rewriter.calls == []


async def test_rag_filter_drops_low_similarity():
    agent, retriever, rewriter = _agent()
    answer = await agent.answer("ktor client", mode="rag_filter")
    ids = [h.chunk_id for h in answer.sources]
    assert "c2" not in ids
    assert retriever.queries[0][1] == 30
    assert rewriter.calls == []


async def test_rag_rewrite_uses_rewritten_query():
    agent, retriever, rewriter = _agent()
    answer = await agent.answer("Как настроить Ktor?", mode="rag_rewrite")
    assert rewriter.calls == ["Как настроить Ktor?"]
    assert retriever.queries[0][0] == "ktor client setup"
    assert len(answer.sources) == 3


async def test_rag_full_combines_rewrite_and_filter():
    agent, retriever, rewriter = _agent()
    answer = await agent.answer("Как настроить Ktor?", mode="rag_full")
    assert rewriter.calls == ["Как настроить Ktor?"]
    assert retriever.queries[0][0] == "ktor client setup"
    assert retriever.queries[0][1] == 30
    assert [h.chunk_id for h in answer.sources] == ["c1", "c3"]


async def test_k_post_caps_sources():
    agent, _, _ = _agent(k_post=1)
    answer = await agent.answer("вопрос", mode="rag")
    assert len(answer.sources) == 1


async def test_rerank_prefers_lexical_overlap_over_similarity():
    hits = [
        Hit("a", "docs/a.md", "A", "S", 0.50, "nothing relevant here"),
        Hit("b", "docs/b.md", "B", "S", 0.45, "ktor client usage"),
    ]
    agent, _, _ = _agent(hits=hits)
    answer = await agent.answer("ktor client", mode="rag_filter")
    assert answer.sources[0].chunk_id == "b"
