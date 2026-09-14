import pytest
from dataclasses import replace
from fastapi.testclient import TestClient

from app.domain.models import (
    AgentResult,
    CompressionInfo,
    ContextLimitExceeded,
    AgentStage,
    AuthenticationGatewayError,
    Chat,
    ChatMessage,
    ChatNotFound,
    ChatSummary,
    GatewayTimeoutError,
    LLMGatewayError,
    RateLimitGatewayError,
    TokenUsage,
    UsageReport,
)
from app.main import app
from app.presentation.dependencies import get_agent, get_repository


def sample_report() -> UsageReport:
    return UsageReport(
        request_tokens=8,
        history_tokens=120,
        response_tokens=20,
        prompt_tokens_api=128,
        completion_tokens_api=20,
        total_tokens_api=148,
        dialog_total_tokens=148,
        dialog_cost_usd=0.00042,
        context_limit=8000,
        context_remaining=7872,
        warning=False,
    )


class FakeRepository:
    def __init__(self):
        self.error = None
        self.deleted = []
        self.chat = Chat(
            id="chat-1",
            title="Новый чат",
            created_at="2026-09-13T12:00:00+00:00",
            updated_at="2026-09-13T12:00:00+00:00",
            messages=[
                ChatMessage(role="user", content="Меня зовут Анна"),
                ChatMessage(
                    role="assistant",
                    content="Приятно познакомиться",
                    usage=TokenUsage(
                        prompt_tokens=100,
                        completion_tokens=20,
                        total_tokens=120,
                    ),
                ),
            ],
            summary="Свёртка диалога.",
            summary_covers=6,
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

    async def delete_chat(self, chat_id):
        if self.error:
            raise self.error
        if chat_id != self.chat.id:
            raise ChatNotFound(chat_id)
        self.deleted.append(chat_id)


class FakeAgent:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    async def run(self, chat_id, message, compress=True):
        self.calls.append((chat_id, message, compress))
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
            usage=sample_report(),
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
    assert [
        {"role": m["role"], "content": m["content"]}
        for m in response.json()["messages"]
    ] == [
        {"role": "user", "content": "Меня зовут Анна"},
        {"role": "assistant", "content": "Приятно познакомиться"},
    ]


def test_get_chat_returns_message_and_dialog_usage(client):
    response = client[0].get("/api/chats/chat-1")

    payload = response.json()
    assert payload["messages"][0]["usage"] is None
    assert payload["messages"][1]["usage"] == {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
    }
    dialog = payload["dialog_usage"]
    assert dialog["dialog_total_tokens"] == 120
    assert dialog["context_limit"] == 8000
    assert dialog["history_tokens"] > 0
    assert 0 <= dialog["context_remaining"] < 8000


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
    assert client[2].calls == [("chat-1", "Как меня зовут?", True)]


def test_unknown_chat_returns_404(client):
    client[1].error = ChatNotFound("missing")

    response = client[0].get("/api/chats/missing")

    assert response.status_code == 404


def test_delete_chat_returns_no_content(client):
    response = client[0].delete("/api/chats/chat-1")

    assert response.status_code == 204
    assert client[1].deleted == ["chat-1"]


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


def test_send_message_returns_usage_breakdown(client):
    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "Как меня зовут?"},
    )

    assert response.status_code == 200
    usage = response.json()["usage"]
    assert usage["request_tokens"] == 8
    assert usage["history_tokens"] == 120
    assert usage["response_tokens"] == 20
    assert usage["prompt_tokens_api"] == 128
    assert usage["dialog_total_tokens"] == 148
    assert usage["context_limit"] == 8000
    assert usage["warning"] is False


def test_send_message_over_budget_returns_413(client):
    fake_agent = FakeAgent(
        error=ContextLimitExceeded(estimated_tokens=8400, context_limit=8000)
    )
    app.dependency_overrides[get_agent] = lambda: fake_agent

    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "привет"},
    )

    assert response.status_code == 413
    assert response.json()["estimated_tokens"] == 8400
    assert response.json()["context_limit"] == 8000
    assert "превысил лимит контекста" in response.json()["detail"]
    assert "новый чат" in response.json()["detail"].lower()


def sample_compression():
    return CompressionInfo(
        applied=True,
        before_tokens=12000,
        after_tokens=1500,
        saved_tokens=10500,
        saved_percent=88,
        summarization_tokens=8000,
        summarization_cost_usd=0.0024,
    )


class RecordingAgent:
    def __init__(self):
        self.kwargs = None

    async def run(self, chat_id, message, compress=True):
        self.kwargs = {"chat_id": chat_id, "message": message, "compress": compress}
        base = sample_report()
        return AgentResult(
            answer="ok",
            model="fake",
            duration_ms=5,
            stages=[AgentStage(name="Agent", status="completed")],
            usage=replace(base, compression=sample_compression()),
        )


def test_message_endpoint_passes_compress_and_reports_compression(client):
    agent = RecordingAgent()
    app.dependency_overrides[get_agent] = lambda: agent
    response = client[0].post(
        "/api/chats/chat-1/messages",
        json={"message": "привет", "compress": False},
    )

    assert response.status_code == 200
    assert agent.kwargs["compress"] is False
    compression = response.json()["usage"]["compression"]
    assert compression["applied"] is True
    assert compression["saved_percent"] == 88


def test_message_endpoint_compression_null_by_default(client):
    response = client[0].post(
        "/api/chats/chat-1/messages", json={"message": "привет"}
    )

    assert response.status_code == 200
    assert response.json()["usage"]["compression"] is None


def test_chat_detail_exposes_summary(client):
    payload = client[0].get("/api/chats/chat-1").json()

    assert payload["summary"] == "Свёртка диалога."
    assert payload["summary_covers"] == 6
