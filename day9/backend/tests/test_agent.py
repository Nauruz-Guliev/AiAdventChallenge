import pytest

from app.application.agent import SYSTEM_PROMPT, Agent
from app.domain.models import (
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
        self.chat = Chat(
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
    huge_history = Chat(
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
    repository.chat = Chat(
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
    repository.chat = Chat(
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


class CompressionRepository:
    def __init__(self, history):
        self.chat = Chat(
            id="chat-1",
            title="Т",
            created_at="2026-09-14T12:00:00+00:00",
            updated_at="2026-09-14T12:00:00+00:00",
            messages=list(history),
        )
        self.summaries = []

    def replace_like(self, summary=None, covers=None, extra=()):
        chat = self.chat
        return Chat(
            id=chat.id,
            title=chat.title,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            messages=[*chat.messages, *extra],
            summary=chat.summary if summary is None else summary,
            summary_covers=chat.summary_covers if covers is None else covers,
        )

    async def get_chat(self, chat_id):
        return self.chat

    async def save_summary(self, chat_id, summary, covers):
        self.summaries.append((chat_id, summary, covers))
        self.chat = self.replace_like(summary=summary, covers=covers)
        return self.chat

    async def append_exchange(self, chat_id, user_content, assistant_content, usage):
        self.chat = self.replace_like(extra=[
            ChatMessage(role="user", content=user_content),
            ChatMessage(role="assistant", content=assistant_content, usage=usage),
        ])
        return self.chat


def long_history(pairs=12):
    filler = " " + "информация " * 60
    history = []
    for index in range(pairs):
        history.append(ChatMessage(role="user", content=f"вопрос {index}{filler}"))
        history.append(ChatMessage(role="assistant", content=f"ответ {index}{filler}"))
    return history


def build_compression_agent(gateway, repository):
    return make_agent(
        gateway, repository, config=UsageConfig(context_limit_tokens=20000)
    )


@pytest.mark.asyncio
async def test_no_compression_below_threshold():
    repo = CompressionRepository([ChatMessage(role="user", content="короткий")])
    gateway = ScriptedGateway([sample_llm_response()])

    result = await build_compression_agent(gateway, repo).run("chat-1", "ещё вопрос")

    assert result.usage.compression is None
    assert len(gateway.calls) == 1


@pytest.mark.asyncio
async def test_compression_sums_up_then_sends_tail():
    repo = CompressionRepository(long_history())
    summary_response = LLMResponse(
        "Итог: пользователь обсуждал информацию.",
        "fake-model",
        TokenUsage(prompt_tokens=9000, completion_tokens=100, total_tokens=9100),
    )
    gateway = ScriptedGateway([summary_response, sample_llm_response()])

    result = await build_compression_agent(gateway, repo).run(
        "chat-1", "что я просил в начале?"
    )

    assert len(gateway.calls) == 2
    summarization_call, main_call = gateway.calls
    assert summarization_call[0].role == "system"
    assert main_call[0].content == SYSTEM_PROMPT
    assert main_call[1].role == "system" and "Итог:" in main_call[1].content
    assert len(main_call) == 1 + 1 + 10 + 1
    assert repo.summaries == [("chat-1", "Итог: пользователь обсуждал информацию.", 14)]
    compression = result.usage.compression
    assert compression.applied is True
    assert compression.before_tokens > compression.after_tokens
    assert compression.saved_tokens == (
        compression.before_tokens - compression.after_tokens
    )
    assert compression.summarization_tokens == 9100
    assert result.usage.history_tokens == compression.after_tokens


@pytest.mark.asyncio
async def test_compression_reuses_cached_summary():
    history = long_history()
    repo = CompressionRepository(history)
    repo.chat = repo.replace_like(summary="готовая свёртка", covers=14)
    gateway = ScriptedGateway([sample_llm_response()])

    result = await build_compression_agent(gateway, repo).run("chat-1", "продолжим")

    assert len(gateway.calls) == 1
    assert "готовая свёртка" in gateway.calls[0][1].content
    assert result.usage.compression.applied is True
    assert result.usage.compression.summarization_tokens == 0


@pytest.mark.asyncio
async def test_compress_disabled_sends_full_history():
    repo = CompressionRepository(long_history())
    gateway = ScriptedGateway([sample_llm_response()])

    result = await build_compression_agent(gateway, repo).run(
        "chat-1", "вопрос", compress=False
    )

    assert len(gateway.calls) == 1
    assert len(gateway.calls[0]) == 1 + 24 + 1
    assert result.usage.compression is None


@pytest.mark.asyncio
async def test_compression_cannot_rescue_giant_tail():
    huge = [
        ChatMessage(role="user", content="токен " * 3000),
        ChatMessage(role="assistant", content="ответ " * 3000),
    ]
    repo = CompressionRepository(huge)
    gateway = ScriptedGateway([])
    agent = make_agent(
        gateway, repo, config=UsageConfig(context_limit_tokens=10000)
    )

    with pytest.raises(ContextLimitExceeded):
        await agent.run("chat-1", "ещё")


@pytest.mark.asyncio
async def test_summary_persisted_before_main_call_and_survives_error():
    repo = CompressionRepository(long_history())
    gateway = ScriptedGateway(
        [
            LLMResponse("свёртка", "fake-model", sample_usage()),
            LLMGatewayError("boom"),
        ]
    )

    with pytest.raises(LLMGatewayError):
        await build_compression_agent(gateway, repo).run("chat-1", "вопрос")

    assert repo.summaries == [("chat-1", "свёртка", 14)]
