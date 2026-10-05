import pytest
from fastapi.testclient import TestClient

from app.application.agent import RAGAgent
from app.application.evaluator import Evaluator
from app.domain.models import Hit
from app.infrastructure.fake_llm import FakeLLM
from app.infrastructure.settings import Settings
from app.main import app
from app.presentation.dependencies import (
    get_agent,
    get_evaluator,
    get_questions,
    get_settings,
)


class StubRetriever:
    def search(self, question, top_k=4):
        return [Hit("c1", "docs/a.md", "A", "Intro", 0.9, "alpha")]


@pytest.fixture
def client(tmp_path):
    agent = RAGAgent(gateway=FakeLLM(answer="ответ"), retriever=StubRetriever())
    evaluator = Evaluator(agent=agent, gateway=FakeLLM(judge_score=1.0))
    settings = Settings(
        eval_report_path=str(tmp_path / "report.json"),
        eval_questions_path=str(tmp_path / "questions.json"),
    )
    app.dependency_overrides[get_agent] = lambda: agent
    app.dependency_overrides[get_evaluator] = lambda: evaluator
    app.dependency_overrides[get_questions] = lambda: []
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_answer_returns_both_modes(client):
    response = client.post("/api/answer", json={"question": "как работает expect/actual?"})
    assert response.status_code == 200
    body = response.json()
    assert body["no_rag"]["mode"] == "no_rag"
    assert body["rag"]["mode"] == "rag"
    assert body["rag"]["sources"][0]["source"] == "docs/a.md"


def test_answer_blank_returns_422(client):
    assert client.post("/api/answer", json={"question": "   "}).status_code == 422


def test_eval_returns_report(client):
    response = client.post("/api/eval")
    assert response.status_code == 200
    assert response.json()["summary"]["questions"] == 0


def test_questions_endpoint(client):
    assert client.get("/api/questions").json() == []
