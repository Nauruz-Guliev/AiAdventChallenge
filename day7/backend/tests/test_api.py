import pytest
from fastapi.testclient import TestClient

from app.domain.models import (
    AgentResult,
    AgentStage,
    AuthenticationGatewayError,
    GatewayTimeoutError,
    LLMGatewayError,
    RateLimitGatewayError,
)
from app.main import app
from app.presentation.dependencies import get_agent


class FakeAgent:
    def __init__(self, error=None):
        self.error = error
        self.messages = []

    async def run(self, message):
        self.messages.append(message)
        if self.error:
            raise self.error
        return AgentResult(
            answer="fake answer",
            model="deepseek-chat",
            duration_ms=4,
            stages=[
                AgentStage(name="UI", status="completed"),
                AgentStage(name="Agent", status="completed"),
                AgentStage(name="DeepSeek API", status="completed"),
            ],
        )


@pytest.fixture
def client():
    fake = FakeAgent()
    app.dependency_overrides[get_agent] = lambda: fake
    with TestClient(app) as test_client:
        yield test_client, fake
    app.dependency_overrides.clear()


def test_chat_returns_agent_result(client):
    test_client, fake = client

    response = test_client.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "fake answer",
        "model": "deepseek-chat",
        "duration_ms": 4,
        "stages": [
            {"name": "UI", "status": "completed"},
            {"name": "Agent", "status": "completed"},
            {"name": "DeepSeek API", "status": "completed"},
        ],
    }
    assert fake.messages == ["hello"]


def test_chat_rejects_blank_message(client):
    response = client[0].post("/api/chat", json={"message": "   "})

    assert response.status_code == 422


def test_chat_rejects_long_message(client):
    response = client[0].post("/api/chat", json={"message": "x" * 4001})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (AuthenticationGatewayError(), 502, "Провайдер отклонил API-ключ. Проверьте .env."),
        (RateLimitGatewayError(), 429, "Провайдер временно ограничил запросы. Повторите позже."),
        (GatewayTimeoutError(), 504, "Провайдер не ответил вовремя. Повторите запуск."),
        (LLMGatewayError(), 502, "Не удалось получить ответ от провайдера."),
    ],
)
def test_chat_maps_provider_errors(client, error, status_code, detail):
    fake = FakeAgent(error=error)
    app.dependency_overrides[get_agent] = lambda: fake

    response = client[0].post("/api/chat", json={"message": "hello"})

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
