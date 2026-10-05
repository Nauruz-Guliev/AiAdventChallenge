from app.application.agent import RAGAgent, build_context
from app.domain.models import Hit
from app.infrastructure.fake_llm import FakeLLM


class RecordingFakeLLM(FakeLLM):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return await super().complete(messages)


class StubRetriever:
    def search(self, question, top_k=4):
        return [Hit("c1", "docs/a.md", "A", "Intro", 0.9, "alpha")]


async def test_no_rag_sends_only_question():
    llm = RecordingFakeLLM(answer="x")
    agent = RAGAgent(gateway=llm, retriever=StubRetriever(), top_k=4)
    answer = await agent.answer("что такое KMP?", mode="no_rag")
    assert answer.mode == "no_rag"
    assert answer.sources == ()
    assert llm.calls[0][1]["content"] == "что такое KMP?"


async def test_rag_injects_context_and_returns_sources():
    llm = RecordingFakeLLM(answer="x")
    agent = RAGAgent(gateway=llm, retriever=StubRetriever(), top_k=4)
    answer = await agent.answer("что такое KMP?", mode="rag")
    assert answer.mode == "rag"
    assert len(answer.sources) == 1
    user = llm.calls[0][1]["content"]
    assert "alpha" in user
    assert "docs/a.md" in user


def test_build_context_labels_hits():
    ctx = build_context([Hit("c1", "docs/a.md", "A", "Intro", 0.9, "alpha")])
    assert "[1] docs/a.md :: Intro" in ctx
    assert "alpha" in ctx
