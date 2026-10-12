from app.application.optimization.profiles import get_profile, get_quant
from app.application.prompt import NO_ANSWER_TEXT
from app.application.rag_service import RagService
from app.config import Settings
from app.domain.models import Hit
from app.infrastructure.heuristic_reranker import HeuristicReranker
from app.ports.llm import Completion


class FakeRetriever:
    def __init__(self, sim=0.9):
        self.sim = {"c0": sim}

    def search(self, question, top_k=None):
        return [Hit("c0", "doc.md", "T", "S", self.sim["c0"], "Kotlin shares code.")]

    def similarity(self, text, chunk_id):
        return self.sim.get(chunk_id, 0.0)

    def chunk_count(self):
        return 1


class FakeLLM:
    def __init__(self, text="ok [1]"):
        self._text = text
        self.kwargs = {}

    async def complete(self, messages, think=False, options=None, model=None):
        self.kwargs = {"think": think, "options": options, "model": model, "messages": messages}
        return Completion(text=self._text)


def _svc(sim=0.9):
    llm = FakeLLM()
    s = Settings(_env_file=None, telegram_bot_token="1:x")
    return RagService(FakeRetriever(sim), HeuristicReranker(), llm, s), llm


async def test_answer_applies_profile_and_model():
    svc, llm = _svc()
    prof = get_profile("optimized")
    quant = get_quant("q8")
    out = await svc.answer("kmp?", [], use_rag=True, profile=prof, model=quant.model)
    assert out.answerable is True and out.sources
    assert llm.kwargs["options"]["temperature"] == 0.2
    assert llm.kwargs["model"] == "gemma4:12b-it-q8_0"


async def test_answer_unanswerable_returns_no_answer():
    svc, _ = _svc(sim=0.1)
    out = await svc.answer("quantum", [], use_rag=True)
    assert out.answerable is False and out.reply == NO_ANSWER_TEXT


def test_prepare_uses_prompt_key():
    svc, _ = _svc()
    p = svc.prepare("kmp?", use_rag=True, prompt_key="optimized")
    assert "Не нашёл в базе" in p.messages[0].content
