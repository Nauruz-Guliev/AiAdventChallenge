import pytest

from app.application.agent import Agent
from app.domain.models import AgentResult, AgentStage, LLMResponse
from app.domain.models import InvalidUserMessage, LLMGatewayError


def test_result_contains_answer_model_duration_and_stages():
    result = AgentResult(
        answer="test answer",
        model="deepseek-chat",
        duration_ms=12,
        stages=[AgentStage(name="Agent", status="completed")],
    )

    assert result.answer == "test answer"
    assert result.model == "deepseek-chat"
    assert result.stages[0].status == "completed"


def test_llm_response_contains_text_and_model():
    response = LLMResponse(text="hello", model="deepseek-chat")

    assert response.text == "hello"


class FakeGateway:
    def __init__(self, response=None, error=None):
        self.response = response or LLMResponse("fake answer", "deepseek-chat")
        self.error = error
        self.messages = None

    async def complete(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_agent_sends_user_message_and_returns_answer():
    gateway = FakeGateway()

    result = await Agent(gateway).run("  hello  ")

    assert result.answer == "fake answer"
    assert gateway.messages[-1].role == "user"
    assert gateway.messages[-1].content == "hello"
    assert [stage.status for stage in result.stages] == ["completed"] * 3


@pytest.mark.asyncio
async def test_agent_rejects_blank_message():
    with pytest.raises(InvalidUserMessage):
        await Agent(FakeGateway()).run("   ")


@pytest.mark.asyncio
async def test_agent_preserves_gateway_error():
    with pytest.raises(LLMGatewayError):
        await Agent(FakeGateway(error=LLMGatewayError("provider failed"))).run("hello")
