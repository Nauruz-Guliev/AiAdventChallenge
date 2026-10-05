import pytest
from fastapi.testclient import TestClient

from app.application.chat_service import ChatService
from app.domain.models import Hit
from app.infrastructure.fake_llm import FakeLLM
from app.infrastructure.heuristic_reranker import HeuristicReranker
from app.infrastructure.session_store import SessionStore
from app.main import app
from app.presentation.dependencies import get_chat_service, get_store


class StubRetriever:
    def search(self, question, top_k=4):
        return [Hit("c1", "docs/a.md", "A", "Intro", 0.9, "alpha")]

    def similarity(self, text, chunk_id):
        return 0.9


class StubRewriter:
    async def rewrite(self, question):
        return "kotlin multiplatform"


def _service():
    llm = FakeLLM(
        answer="alpha [1]",
        memory={"goal": "цель", "constraints": ["ограничение"], "clarifications": [], "terms": []},
    )
    return ChatService(
        gateway=llm,
        retriever=StubRetriever(),
        reranker=HeuristicReranker(),
        rewriter=StubRewriter(),
        min_quote_len=3,
        no_answer_min_score=0.0,
    )


@pytest.fixture
def client(tmp_path):
    service = _service()
    store = SessionStore(tmp_path)
    app.dependency_overrides[get_chat_service] = lambda: service
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_session_and_send_message(client):
    created = client.post("/api/sessions", json={"goal": "цель"}).json()
    sid = created["id"]
    assert created["memory"]["goal"] == "цель"

    turn = client.post(f"/api/sessions/{sid}/messages", json={"text": "вопрос"}).json()
    assert turn["reply"] == "alpha [1]"
    assert turn["sources"][0]["source"] == "docs/a.md"
    assert turn["citations"][0]["grounded"] is True
    assert turn["memory"]["constraints"] == ["ограничение"]

    session = client.get(f"/api/sessions/{sid}").json()
    assert len(session["messages"]) == 2


def test_list_sessions(client):
    client.post("/api/sessions", json={"goal": "цель"})
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["goal"] == "цель"


def test_blank_message_returns_422(client):
    created = client.post("/api/sessions", json={"goal": "цель"}).json()
    response = client.post(f"/api/sessions/{created['id']}/messages", json={"text": "   "})
    assert response.status_code == 422


def test_missing_session_returns_404(client):
    assert client.get("/api/sessions/nope").status_code == 404
