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

    async def append_exchange(self, chat_id, user_content, assistant_content, usage, branch_id=None, mode=None):
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



class ScriptedGateway:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(list(messages))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class ModeRepository:
    def __init__(self, chat):
        self.chat = chat
        self.saved_facts = []
        self.modes = []

    async def get_chat(self, chat_id):
        return self.chat

    async def save_facts(self, chat_id, branch_id, facts):
        self.saved_facts.append((branch_id, dict(facts)))
        self.chat.active_branch.facts = dict(facts)
        return self.chat

    async def append_exchange(
        self, chat_id, user_content, assistant_content, usage, branch_id=None, mode=None
    ):
        self.modes.append(mode)
        branch = next(b for b in self.chat.branches if b.id == (branch_id or self.chat.active_branch_id))
        branch.messages.extend(
            [
                ChatMessage(role="user", content=user_content),
                ChatMessage(role="assistant", content=assistant_content, usage=usage),
            ]
        )
        return self.chat


def mode_chat(count=10, facts=None):
    branch = Branch(
        id="b1",
        name="main",
        messages=[ChatMessage(role="user", content=f"u{i}") for i in range(count)],
        facts=facts if facts is not None else {},
    )
    return Chat(
        id="c1",
        title="T",
        created_at="2026-09-14T00:00:00+00:00",
        updated_at="2026-09-14T00:00:00+00:00",
        branches=[branch],
        active_branch_id="b1",
    )


def scripted_response(text="ok", prompt=9, completion=3):
    return LLMResponse(
        text=text,
        model="m",
        usage=TokenUsage(prompt, completion, prompt + completion),
    )


@pytest.mark.asyncio
async def test_full_mode_sends_everything():
    gateway = ScriptedGateway([scripted_response()])
    repository = ModeRepository(mode_chat(10))

    result = await make_agent(gateway, repository).run("c1", "новое", mode="full")

    assert len(gateway.calls[0]) == 10 + 2
    assert result.usage.context.mode == "full"
    assert result.usage.context.fact_update_tokens == 0


@pytest.mark.asyncio
async def test_sliding_mode_window_only():
    gateway = ScriptedGateway([scripted_response()])
    repository = ModeRepository(mode_chat(10))
    config = UsageConfig(sliding_window_messages=4)

    result = await make_agent(gateway, repository, config).run(
        "c1", "новое", mode="sliding"
    )

    sent = gateway.calls[0]
    assert len(sent) == 1 + 4 + 1
    assert result.usage.context.sent_messages == 4
    assert result.usage.context.total_messages == 10


@pytest.mark.asyncio
async def test_facts_mode_extracts_then_prepends_and_saves():
    chat = mode_chat(1, facts={})
    chat.active_branch.messages = [ChatMessage(role="user", content="бюджет 1200")]
    gateway = ScriptedGateway(
        [
            scripted_response('{"бюджет": "1200"}', prompt=40, completion=10),
            scripted_response("ok", prompt=30, completion=5),
        ]
    )
    repository = ModeRepository(chat)

    result = await make_agent(gateway, repository).run(
        "c1", "бюджет 1200", mode="facts"
    )

    assert repository.saved_facts == [("b1", {"бюджет": "1200"})]
    assert repository.modes == ["facts"]
    main_call = gateway.calls[1]
    assert main_call[1].role == "system" and "бюджет: 1200" in main_call[1].content
    assert result.usage.context.fact_update_tokens == 50
    assert result.usage.context.fact_update_cost_usd > 0


@pytest.mark.asyncio
async def test_facts_mode_garbage_extraction_keeps_old():
    chat = mode_chat(1, facts={"старый": "факт"})
    gateway = ScriptedGateway(
        [
            scripted_response("не json вовсе", prompt=40, completion=10),
            scripted_response("ok", prompt=30, completion=5),
        ]
    )
    repository = ModeRepository(chat)

    await make_agent(gateway, repository).run("c1", "у", mode="facts")

    assert repository.saved_facts == []
    assert repository.chat.facts == {"старый": "факт"}


@pytest.mark.asyncio
async def test_precheck_uses_assembled_not_full_history():
    chat = mode_chat(20)
    chat.active_branch.messages = [
        ChatMessage(role="user", content="x" * 400) for _ in range(20)
    ]
    config = UsageConfig(
        context_limit_tokens=600, sliding_window_messages=4
    )
    gateway = ScriptedGateway([scripted_response()])
    agent = make_agent(gateway, ModeRepository(chat), config)

    result = await agent.run("c1", "y", mode="sliding")
    assert result.usage.context.mode == "sliding"

    with pytest.raises(ContextLimitExceeded):
        await agent.run("c1", "y", mode="full")
