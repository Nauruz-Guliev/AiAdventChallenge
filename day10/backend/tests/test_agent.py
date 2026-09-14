import pytest

from app.application.agent import SYSTEM_PROMPT, Agent
from app.domain.models import (
    Branch,
    Chat,
    ChatMessage,
    ContextLimitExceeded,
    InvalidUserMessage,
    LLMGatewayError,
    LLMResponse,
    TokenUsage,
    UsageConfig,
    UsageReport,
)
from app.infrastructure.token_counter import TiktokenCounter


def sample_usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120)


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
        self.chat = _chat(
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
        self.chat = _chat(
            id=self.chat.id,
            title=self.chat.title,
            created_at=self.chat.created_at,
            updated_at=self.chat.updated_at,
            messages=[
                *self.chat.messages,
                ChatMessage(role="user", content=user_content),
                ChatMessage(
                    role="assistant", content=assistant_content, usage=usage
                ),
            ],
        )
        return self.chat


def make_agent(gateway=None, repository=None, config=None):
    return Agent(
        gateway or FakeGateway(),
        repository or FakeRepository(),
        counter=TiktokenCounter(),
        config=config or UsageConfig(),
    )


@pytest.mark.asyncio
async def test_agent_sends_previous_history_and_saves_exchange():
    gateway = FakeGateway()
    repository = FakeRepository()

    result = await make_agent(gateway, repository).run("chat-1", "Как меня зовут?")

    assert [message.role for message in gateway.messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert gateway.messages[-1].content == "Как меня зовут?"
    assert repository.saved[:3] == ("chat-1", "Как меня зовут?", result.answer)
    assert repository.saved[3] == sample_usage()


@pytest.mark.asyncio
async def test_agent_returns_usage_report_split_and_totals():
    result = await make_agent().run("chat-1", "Как меня зовут?")

    usage = result.usage
    assert usage.request_tokens > 0
    assert usage.history_tokens > 0
    assert usage.response_tokens == 20
    assert usage.prompt_tokens_api == 100
    assert usage.total_tokens_api == 120
    assert usage.dialog_total_tokens == 120
    assert usage.dialog_cost_usd == pytest.approx(
        (100 * 0.30 + 20 * 1.20) / 1_000_000
    )
    assert usage.context_limit == 8000
    assert 0 < usage.context_remaining < 8000


@pytest.mark.asyncio
async def test_agent_blocks_request_over_context_budget():
    gateway = FakeGateway()
    repository = FakeRepository()
    huge_history = _chat(
        id="chat-1",
        title="Длинный",
        created_at="2026-09-13T12:00:00+00:00",
        updated_at="2026-09-13T12:00:00+00:00",
        messages=[
            ChatMessage(role="user", content="токен " * 3000),
            ChatMessage(role="assistant", content="ok"),
        ],
    )

    class BigChatRepository(FakeRepository):
        async def get_chat(self, chat_id):
            return huge_history

    agent = make_agent(
        gateway,
        BigChatRepository(),
        config=UsageConfig(context_limit_tokens=2000),
    )

    with pytest.raises(ContextLimitExceeded) as excinfo:
        await agent.run("chat-1", "Привет")

    assert excinfo.value.estimated_tokens > 2000
    assert excinfo.value.context_limit == 2000
    assert gateway.messages is None
    assert repository.saved is None


@pytest.mark.asyncio
async def test_agent_warning_when_budget_nearly_full():
    repository = FakeRepository()
    repository.chat = _chat(
        id="chat-1",
        title="Почти полный",
        created_at="2026-09-13T12:00:00+00:00",
        updated_at="2026-09-13T12:00:00+00:00",
        messages=[ChatMessage(role="user", content="токен " * 560)],
    )

    result = await make_agent(
        FakeGateway(),
        repository,
        config=UsageConfig(context_limit_tokens=2000),
    ).run("chat-1", "Привет")

    assert result.usage.warning is True


@pytest.mark.asyncio
async def test_agent_sends_user_message_and_returns_answer():
    gateway = FakeGateway()

    result = await make_agent(gateway).run("chat-1", "  hello  ")

    assert result.answer == "fake answer"
    assert gateway.messages[-1].content == "hello"
    assert [stage.status for stage in result.stages] == ["completed"] * 3


@pytest.mark.asyncio
async def test_agent_rejects_blank_message():
    with pytest.raises(InvalidUserMessage):
        await make_agent().run("chat-1", "   ")


@pytest.mark.asyncio
async def test_agent_preserves_gateway_error():
    with pytest.raises(LLMGatewayError):
        await make_agent(
            FakeGateway(error=LLMGatewayError("provider failed")),
        ).run("chat-1", "hello")


@pytest.mark.asyncio
async def test_over_budget_message_is_not_saved():
    repository = FakeRepository()
    repository.chat = _chat(
        id="chat-1",
        title="Т",
        created_at="2026-09-13T12:00:00+00:00",
        updated_at="2026-09-13T12:00:00+00:00",
        messages=[ChatMessage(role="user", content="токен " * 1400)],
    )

    with pytest.raises(ContextLimitExceeded):
        await make_agent(
            FakeGateway(),
            repository,
            config=UsageConfig(context_limit_tokens=1500),
        ).run("chat-1", "Привет ещё раз")

    assert repository.saved is None


def sample_llm_response() -> LLMResponse:
    return LLMResponse("fake answer", "deepseek-chat", sample_usage())


class ScriptedGateway:
    """Отдаёт responses по порядку; пишет все вызовы в .calls."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _chat(id, title, created_at, updated_at, messages):
    branch = Branch(id=f"{id}-b1", name="main", messages=list(messages))
    return Chat(
        id=id,
        title=title,
        created_at=created_at,
        updated_at=updated_at,
        branches=[branch],
        active_branch_id=branch.id,
    )

