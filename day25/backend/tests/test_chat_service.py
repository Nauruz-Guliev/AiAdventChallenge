from app.application.chat_service import ChatService
from app.domain.models import Hit, Session, TaskMemory
from app.infrastructure.fake_llm import FakeLLM
from app.infrastructure.heuristic_reranker import HeuristicReranker


class StubRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, question, top_k=4):
        return self.hits[:top_k]

    def similarity(self, text, chunk_id):
        return next((h.score for h in self.hits if h.chunk_id == chunk_id), 0.0)


class StubRewriter:
    def __init__(self, query="ktor client"):
        self.query = query
        self.calls = []

    async def rewrite(self, question):
        self.calls.append(question)
        return self.query


def _hits():
    return [
        Hit("c1", "docs/ktor.md", "Ktor", "Client", 0.9, "ktor client usage with HttpClient"),
        Hit("c2", "docs/ktor.md", "Ktor", "Engine", 0.8, "choose engine android okhttp ios darwin"),
    ]


def _service(no_answer_min_score=0.0):
    llm = FakeLLM(
        answer="используйте HttpClient [1]",
        memory={
            "goal": "настроить ktor",
            "constraints": ["kotlin 2.0"],
            "clarifications": ["engine"],
            "terms": [],
        },
    )
    return ChatService(
        gateway=llm,
        retriever=StubRetriever(_hits()),
        reranker=HeuristicReranker(),
        rewriter=StubRewriter(),
        min_quote_len=3,
        no_answer_min_score=no_answer_min_score,
    )


async def test_answer_returns_reply_sources_and_citations():
    session = Session(id="s1", memory=TaskMemory(goal="настроить ktor"))
    turn = await _service().answer(session, "как создать HttpClient?")
    assert turn.reply == "используйте HttpClient [1]"
    assert turn.sources[0].chunk_id == "c1"
    assert len(turn.citations) >= 1
    assert turn.answerable is True


async def test_answer_updates_memory():
    session = Session(id="s1", memory=TaskMemory(goal="настроить ktor"))
    turn = await _service().answer(session, "как создать HttpClient?")
    assert "kotlin 2.0" in turn.memory.constraints
    assert turn.memory.goal == "настроить ktor"


async def test_answer_says_not_know_when_below_threshold():
    session = Session(id="s1", memory=TaskMemory(goal="настроить ktor"))
    turn = await _service(no_answer_min_score=0.99).answer(session, "как создать HttpClient?")
    assert turn.answerable is False
    assert turn.sources == ()
    assert "не нашёл" in turn.reply


async def test_answer_raises_on_blank():
    from app.domain.models import InvalidQuestion

    import pytest
    session = Session(id="s1")
    with pytest.raises(InvalidQuestion):
        await _service().answer(session, "   ")
