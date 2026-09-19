import pytest

from app.application.agent import Agent
from app.domain.models import (
    Chat,
    ChatMessage,
    ContextLimitExceeded,
    InvalidUserMessage,
    LLMResponse,
    LongTermMemory,
    TokenUsage,
    UsageConfig,
    WorkingMemory,
)
from app.infrastructure.token_counter import TiktokenCounter


def usage(prompt=30, completion=5):
    return TokenUsage(prompt, completion, prompt + completion)


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


def response(text="ok", prompt=30, completion=5):
    return LLMResponse(text, "m", usage(prompt, completion))


class MemoryRepository:
    def __init__(self, chat):
        self.chat = chat
        self.long_term = LongTermMemory()
        self.appended = []
        self.candidates = []
        self.entries = []

    async def get_chat(self, chat_id):
        return self.chat

    async def get_long_term(self):
        return self.long_term

    async def append_exchange(self, chat_id, user, assistant, token_usage):
        self.appended.append((user, assistant))
        self.chat.messages.extend(
            [
                ChatMessage(role="user", content=user),
                ChatMessage(role="assistant", content=assistant, usage=token_usage),
            ]
        )
        return self.chat

    async def add_long_term_entry(self, category, text, source_chat_id):
        self.entries.append((category, text))

    async def add_candidates(self, items, source_chat_id):
        self.candidates.append(items)


def make_agent(gateway, repository, config=None, candidates_enabled=True):
    return Agent(
        gateway,
        repository=repository,
        counter=TiktokenCounter(),
        config=config or UsageConfig(),
        candidates_enabled=candidates_enabled,
    )


def sample_chat(working=None):
    return Chat(
        id="c1",
        title="T",
        created_at="a",
        updated_at="b",
        messages=[ChatMessage(role="user", content="привет")],
        working_memory=working or WorkingMemory(),
    )


@pytest.mark.asyncio
async def test_prompt_contains_all_three_layers():
    repository = MemoryRepository(sample_chat(WorkingMemory(goal="Собрать ТЗ")))
    repository.long_term = LongTermMemory()
    gateway = ScriptedGateway([response(), response("[]")])

    await make_agent(gateway, repository).run("c1", "вопрос")

    main_call = gateway.calls[0]
    contents = [m.content for m in main_call]
    assert any("## Рабочая память" in c for c in contents)
    assert any("привет" in c for c in contents)
    assert main_call[-1].content == "вопрос"


@pytest.mark.asyncio
async def test_candidates_are_searched_after_answer():
    repository = MemoryRepository(sample_chat())
    gateway = ScriptedGateway(
        [
            response("ответ"),
            response('[{"text": "аллергия", "category": "knowledge"}]'),
        ]
    )

    await make_agent(gateway, repository).run("c1", "я аллергик")

    assert len(gateway.calls) == 2
    assert repository.candidates == [
        [{"text": "аллергия", "category": "knowledge"}]
    ]
    assert repository.appended == [("я аллергик", "ответ")]


@pytest.mark.asyncio
async def test_memory_command_writes_immediately_without_candidates():
    repository = MemoryRepository(sample_chat())
    gateway = ScriptedGateway(
        [
            response('[{"text": "люблю Kotlin", "category": "profile"}]'),
            response("ок"),
        ]
    )

    result = await make_agent(gateway, repository).run(
        "c1", "запомни: люблю Kotlin"
    )

    assert repository.entries == [("profile", "люблю Kotlin")]
    assert repository.candidates == []
    assert result.answer == "ок"


@pytest.mark.asyncio
async def test_candidates_disabled_skips_second_call():
    repository = MemoryRepository(sample_chat())
    gateway = ScriptedGateway([response("ответ")])

    await make_agent(gateway, repository, candidates_enabled=False).run(
        "c1", "привет"
    )

    assert len(gateway.calls) == 1


@pytest.mark.asyncio
async def test_blank_message_rejected():
    with pytest.raises(InvalidUserMessage):
        await make_agent(
            ScriptedGateway([]), MemoryRepository(sample_chat())
        ).run("c1", "   ")


@pytest.mark.asyncio
async def test_context_limit_exceeded_blocks_message_before_api_call():
    repository = MemoryRepository(sample_chat())
    gateway = ScriptedGateway([])

    with pytest.raises(ContextLimitExceeded):
        await make_agent(
            gateway,
            repository,
            config=UsageConfig(context_limit_tokens=1),
        ).run("c1", "вопрос")

    assert gateway.calls == []
    assert repository.appended == []