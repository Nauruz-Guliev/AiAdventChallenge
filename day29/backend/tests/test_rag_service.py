from app.application.prompt import NO_ANSWER_TEXT
from app.application.rag_service import RagService
from app.config import Settings
from app.domain.models import Hit
from app.infrastructure.heuristic_reranker import HeuristicReranker
from app.ports.llm import Completion


class FakeRetriever:
    def __init__(self, hits):
        self._hits = hits
        self.sim = {}

    def search(self, question, top_k=None):
        return list(self._hits)

    def similarity(self, text, chunk_id):
        return self.sim.get(chunk_id, 0.0)

    def chunk_count(self):
        return len(self._hits)


class FakeLLM:
    def __init__(self, text="Ответ [1]"):
        self._text = text
        self.calls = []

    async def complete(self, messages, think=False):
        self.calls.append(messages)
        return Completion(text=self._text)


def _hits():
    return [
        Hit("c0", "doc.md", "T", "S", 0.9, "Kotlin Multiplatform shares code."),
        Hit("c1", "doc.md", "T", "S", 0.8, "Other text."),
    ]


def _settings(**kw):
    return Settings(_env_file=None, telegram_bot_token="1:x", top_k_pre=30, top_k_post=2, **kw)


def test_prepare_answerable_builds_context():
    r = FakeRetriever(_hits())
    r.sim = {"c0": 0.9, "c1": 0.8}
    svc = RagService(r, HeuristicReranker(), FakeLLM(), _settings())
    p = svc.prepare("what is kmp?")
    assert p.answerable is True
    assert p.hits and "Контекст:" in p.messages[-1].content


def test_prepare_unanswerable_when_low_relevance():
    r = FakeRetriever(_hits())
    r.sim = {"c0": 0.1, "c1": 0.1}
    svc = RagService(r, HeuristicReranker(), FakeLLM(), _settings())
    p = svc.prepare("quantum physics")
    assert p.answerable is False


async def test_answer_unanswerable_returns_no_answer():
    r = FakeRetriever(_hits())
    r.sim = {"c0": 0.1, "c1": 0.1}
    svc = RagService(r, HeuristicReranker(), FakeLLM(), _settings())
    out = await svc.answer("quantum", [])
    assert out.answerable is False and out.reply == NO_ANSWER_TEXT


async def test_answer_attaches_sources_and_citations():
    r = FakeRetriever(_hits())
    r.sim = {"c0": 0.9, "c1": 0.8}
    svc = RagService(r, HeuristicReranker(), FakeLLM("it shares code [1]"), _settings())
    out = await svc.answer("kmp?", [])
    assert out.answerable is True and len(out.sources) >= 1
