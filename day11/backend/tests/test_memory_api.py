import json

import pytest
from fastapi.testclient import TestClient

from app.domain.models import (
    AgentResult,
    AgentStage,
    Chat,
    ChatMessage,
    ChatNotFound,
    ContextLimitExceeded,
    InvalidUserMessage,
    MemoryInfo,
    TokenUsage,
    UsageConfig,
    UsageReport,
    WorkingMemory,
)
from app.infrastructure.json_memory_repository import JsonMemoryRepository
from app.main import app
from app.presentation.dependencies import get_agent, get_repository, get_usage_config


def report():
    return UsageReport(
        request_tokens=5,
        history_tokens=20,
        response_tokens=7,
        prompt_tokens_api=25,
        completion_tokens_api=7,
        total_tokens_api=32,
        dialog_total_tokens=32,
        dialog_cost_usd=0.00001,
        context_limit=8000,
        context_remaining=7975,
        warning=False,
        memory=MemoryInfo(0, 0, 0, 20, 9),
    )


class FakeAgent:
    async def run(self, chat_id, message):
        return AgentResult(
            answer="ответ",
            model="deepseek-chat",
            duration_ms=1,
            stages=[AgentStage(name="Agent", status="completed")],
            usage=report(),
        )


@pytest.fixture
def client(tmp_path):
    repository = JsonMemoryRepository(
        chats_dir=tmp_path / "chats",
        long_term_path=tmp_path / "long_term.json",
        candidates_path=tmp_path / "candidates.json",
    )
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_agent] = lambda: FakeAgent()
    app.dependency_overrides[get_usage_config] = lambda: UsageConfig()
    with TestClient(app) as test_client:
        yield test_client, repository
    app.dependency_overrides.clear()


def test_chat_crud_and_clear_history(client):
    http, _ = client
    chat_id = http.post("/api/chats").json()["id"]

    detail = http.get(f"/api/chats/{chat_id}").json()
    assert detail["working_memory"]["status"] == "active"
    assert detail["messages"] == []

    assert http.delete(f"/api/chats/{chat_id}/messages").status_code == 200
    assert http.delete(f"/api/chats/{chat_id}").status_code == 204
    assert http.get(f"/api/chats/{chat_id}").status_code == 404


def test_working_memory_endpoints(client):
    http, _ = client
    chat_id = http.post("/api/chats").json()["id"]

    saved = http.put(
        f"/api/chats/{chat_id}/working-memory",
        json={
            "goal": "Собрать ТЗ",
            "constraints": ["бюджет 900"],
            "decisions": [],
            "status": "active",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["working_memory"]["goal"] == "Собрать ТЗ"

    assert http.post(
        f"/api/chats/{chat_id}/working-memory/complete"
    ).json()["working_memory"]["status"] == "done"
    assert http.post(
        f"/api/chats/{chat_id}/working-memory/reset"
    ).json()["working_memory"]["goal"] == ""


def test_long_term_crud(client):
    http, repository = client
    chat_id = http.post("/api/chats").json()["id"]

    created = http.put(
        "/api/long-term",
        json={
            "profile": [{"id": "e1", "text": "Науруз", "source_chat_id": chat_id, "created_at": "t"}],
            "decisions": [],
            "knowledge": [],
        },
    )
    assert created.status_code == 200
    assert http.get("/api/long-term").json()["profile"][0]["text"] == "Науруз"

    assert http.delete("/api/long-term/profile/e1").status_code == 204
    assert http.delete("/api/long-term/profile/e1").status_code == 404


def test_candidates_approve_reject(client, tmp_path):
    http, repository = client
    chat_id = http.post("/api/chats").json()["id"]

    # Кандидаты заводятся напрямую в файл (отдельного API создания нет).
    (tmp_path / "candidates.json").write_text(
        json.dumps(
            {
                "version": 1,
                "candidates": [
                    {
                        "id": "cand-1",
                        "text": "аллергия",
                        "category": "knowledge",
                        "source_chat_id": chat_id,
                        "status": "pending",
                        "created_at": "t",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert len(http.get("/api/candidates?status=pending").json()) == 1
    approved = http.post("/api/candidates/cand-1/approve")
    assert approved.status_code == 200
    assert approved.json()["text"] == "аллергия"
    assert http.get("/api/long-term").json()["knowledge"][0]["text"] == "аллергия"

    assert http.post("/api/candidates/cand-1/reject").status_code == 409


def test_approve_candidate_choose_where_and_what(client, tmp_path):
    http, repository = client
    chat_id = http.post("/api/chats").json()["id"]
    (tmp_path / "candidates.json").write_text(
        json.dumps(
            {
                "version": 1,
                "candidates": [
                    {"id": "c1", "text": "люблю Kotlin", "category": "knowledge", "source_chat_id": chat_id, "status": "pending", "created_at": "t"},
                    {"id": "c2", "text": "ещё", "category": "knowledge", "source_chat_id": chat_id, "status": "pending", "created_at": "t"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    approved = http.post(
        "/api/candidates/c1/approve",
        json={"category": "profile", "text": "Пишу на Kotlin"},
    )
    assert approved.status_code == 200
    assert approved.json()["text"] == "Пишу на Kotlin"
    long_term = http.get("/api/long-term").json()
    assert long_term["profile"][0]["text"] == "Пишу на Kotlin"
    assert long_term["knowledge"] == []

    assert http.post(
        "/api/candidates/c2/approve", json={"category": "nonsense"}
    ).status_code == 400
    assert http.post(
        "/api/candidates/c2/approve", json={"text": "   "}
    ).status_code == 400


def test_send_message_returns_memory_usage(client):
    http, _ = client
    chat_id = http.post("/api/chats").json()["id"]

    response = http.post(
        f"/api/chats/{chat_id}/messages", json={"message": "привет"}
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "ответ"
    assert response.json()["usage"]["memory"]["candidate_tokens"] == 9


def test_send_message_blank_returns_422(client):
    http, _ = client
    chat_id = http.post("/api/chats").json()["id"]

    assert http.post(
        f"/api/chats/{chat_id}/messages", json={"message": "   "}
    ).status_code == 422


class ErrorAgent:
    def __init__(self, error):
        self._error = error

    async def run(self, chat_id, message):
        raise self._error


def test_agent_errors_mapped_to_status_codes(client):
    http, _ = client
    chat_id = http.post("/api/chats").json()["id"]
    cases = [
        (ChatNotFound("x"), 404),
        (ContextLimitExceeded(9000, 8000), 413),
        (InvalidUserMessage("blank"), 400),
    ]
    for error, status in cases:
        app.dependency_overrides[get_agent] = lambda e=error: ErrorAgent(e)
        response = http.post(
            f"/api/chats/{chat_id}/messages", json={"message": "привет"}
        )
        assert response.status_code == status


def test_route_level_validation_errors(client):
    http, _ = client
    assert http.delete("/api/candidates?status=pending").status_code == 400
    assert http.delete("/api/long-term/unknown/e1").status_code == 404
    assert http.post("/api/candidates/nope/approve").status_code == 404
    assert http.delete("/api/chats/missing").status_code == 404

    app.dependency_overrides[get_usage_config] = lambda: UsageConfig(
        long_term_max_per_category=1
    )
    response = http.put(
        "/api/long-term",
        json={
            "profile": [
                {"id": "a", "text": "один"},
                {"id": "b", "text": "два"},
            ],
            "decisions": [],
            "knowledge": [],
        },
    )
    assert response.status_code == 400