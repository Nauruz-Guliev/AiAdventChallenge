import pytest
from fastapi.testclient import TestClient

from app.domain.models import (
    AgentResult,
    AgentStage,
    AuthenticationGatewayError,
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatSummary,
    GatewayTimeoutError,
    LLMGatewayError,
    RateLimitGatewayError,
)
from app.main import app
from app.presentation.dependencies import get_agent, get_repository


class FakeRepository:
    def __init__(self):
        self.error = None
        self.chat = Chat(
            id="chat-1",
            title="Новый чат",
            created_at="2026-09-13T12:00:00+00:00",
            updated_at="2026-09-13T12:00:00+00:00",
            messages=[
                ChatMessage(role="user", content="Меня зовут Анна"),
                ChatMessage(role="assistant", content="Приятно познакомиться"),
            ],
        )

    async def create_chat(self):
        return self.chat

    async def list_chats(self):
        return [
            ChatSummary(
                id=self.chat.id,
                title=self.chat.title,
                created_at=self.chat.created_at,
                updated_at=self.chat.updated_at,
            )
        ]

    async def get_chat(self, chat_id):
        if self.error:
            raise self.error
        if chat_id != self.chat.id:
            raise ChatNotFound(chat_id)
        return self.chat


class FakeAgent:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    async def run(self, chat_id, message):
        self.calls.append((chat_id, message))
        if self.error:
            raise self.error
        return AgentResult(
            answer="Анна",
            model="deepseek-chat",
            duration_ms=3,
            stages=[
                AgentStage(name="UI", status="completed"),
                AgentStage(name="Agent", status="completed"),
                AgentStage(name="DeepSeek API", status="completed"),
            ],
        )


@pytest.fixture
def client():
    fake_repository = FakeRepository()
    fake_agent = FakeAgent()
    app.dependency_overrides[get_repository] = lambda: fake_repository
    app.dependency_overrides[get_agent] = lambda: fake_agent
    with TestClient(app) as test_client:
        yield test_client, fake_repository, fake_agent
    app.dependency_overrides.clear()


def test_create_chat_returns_summary(client):
    response = client[0].post("/api/chats")

    assert response.status_code == 201
    assert response.json()["title"] == "Новый чат"
    assert response.json()["id"] == "chat-1"


def test_get_chat_returns_history(client):
    response = client[0].get("/api/chats/chat-1")

    assert response.status_code == 200
    assert response.json()["messages"] == [
        {"role": "user", "content": "Меня зовут Анна"},
        {"role": "assistant", "content": "Приятно познакомиться"},
    ]


def test_list_chats_returns_summaries(client):
    response = client[0].get("/api/chats")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "chat-1"
    assert "messages" not in response.json()[0]


def test_send_message_passes_chat_id_to_agent(client):
    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "Как меня зовут?"},
    )

    assert response.status_code == 200
    assert response.json()["chat_id"] == "chat-1"
    assert client[2].calls == [("chat-1", "Как меня зовут?")]


def test_unknown_chat_returns_404(client):
    client[1].error = ChatNotFound("missing")

    response = client[0].get("/api/chats/missing")

    assert response.status_code == 404


def test_send_message_rejects_blank_message(client):
    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "   "},
    )

    assert response.status_code == 422


def test_send_message_rejects_long_message(client):
    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "x" * 4001},
    )

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
def test_send_message_maps_provider_errors(client, error, status_code, detail):
    fake_agent = FakeAgent(error=error)
    app.dependency_overrides[get_agent] = lambda: fake_agent

    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "hello"},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
