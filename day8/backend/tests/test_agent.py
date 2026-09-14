import pytest

from app.application.agent import Agent
from app.domain.models import AgentResult, AgentStage, Chat, ChatMessage, LLMResponse
from app.domain.models import InvalidUserMessage, LLMGatewayError, TokenUsage, UsageReport


def sample_usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120)


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


def test_result_contains_answer_model_duration_and_stages():
    result = AgentResult(
        answer="test answer",
        model="deepseek-chat",
        duration_ms=12,
        stages=[AgentStage(name="Agent", status="completed")],
        usage=sample_report(),
    )

    assert result.answer == "test answer"
    assert result.model == "deepseek-chat"
    assert result.stages[0].status == "completed"


def test_llm_response_contains_text_and_model():
    response = LLMResponse(text="hello", model="deepseek-chat", usage=sample_usage())

    assert response.text == "hello"


class FakeGateway:
    def __init__(self, response=None, error=None):
        self.response = response or LLMResponse(
            "fake answer", "deepseek-chat", sample_usage()
        )
        self.error = error
        self.messages = None

    async def complete(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return self.response


class FakeRepository:
    def __init__(self):
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
        self.saved = None

    async def get_chat(self, chat_id):
        assert chat_id == self.chat.id
        return self.chat

    async def append_exchange(self, chat_id, user_content, assistant_content, usage):
        self.saved = (chat_id, user_content, assistant_content, usage)
        return self.chat


@pytest.mark.asyncio
async def test_agent_sends_previous_history_and_saves_exchange():
    gateway = FakeGateway()
    repository = FakeRepository()

    result = await Agent(gateway, repository).run("chat-1", "Как меня зовут?")

    assert [message.role for message in gateway.messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert gateway.messages[-2].content == "Приятно познакомиться"
    assert gateway.messages[-1].content == "Как меня зовут?"
    assert repository.saved[:3] == ("chat-1", "Как меня зовут?", result.answer)
    assert repository.saved[3] == sample_usage()


@pytest.mark.asyncio
async def test_agent_sends_user_message_and_returns_answer():
    gateway = FakeGateway()

    result = await Agent(gateway, FakeRepository()).run("chat-1", "  hello  ")

    assert result.answer == "fake answer"
    assert gateway.messages[-1].role == "user"
    assert gateway.messages[-1].content == "hello"
    assert [stage.status for stage in result.stages] == ["completed"] * 3


@pytest.mark.asyncio
async def test_agent_rejects_blank_message():
    with pytest.raises(InvalidUserMessage):
        await Agent(FakeGateway(), FakeRepository()).run("chat-1", "   ")


@pytest.mark.asyncio
async def test_agent_preserves_gateway_error():
    with pytest.raises(LLMGatewayError):
        await Agent(
            FakeGateway(error=LLMGatewayError("provider failed")),
            FakeRepository(),
        ).run("chat-1", "hello")
