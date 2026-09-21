from app.application.agent import Agent
from app.domain.invariant import Invariant
from app.domain.models import (
    Chat,
    ChatMessage,
    LLMResponse,
    LongTermMemory,
    TokenUsage,
    UsageConfig,
    WorkingMemory,
)
from app.domain.task_state import Stage, TaskState
from app.infrastructure.token_counter import TiktokenCounter


class ScriptedGateway:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(list(messages))
        return self.responses.pop(0)


class MemoryRepository:
    def __init__(self, chat):
        self.chat = chat
        self.exchanges = []

    async def get_chat(self, chat_id):
        return self.chat

    async def get_long_term(self):
        return LongTermMemory()

    async def append_exchange(self, chat_id, user, assistant, usage, used=None):
        self.exchanges.append((user, assistant))
        self.chat.messages.extend(
            [
                ChatMessage(role="user", content=user),
                ChatMessage(
                    role="assistant", content=assistant, usage=usage, used=used
                ),
            ]
        )
        return self.chat

    async def add_candidates(self, items, source_chat_id):
        pass


class TaskRepository:
    def __init__(self, state=None):
        self.state = state

    async def get(self):
        return self.state

    async def save(self, state):
        self.state = state


class InvariantRepository:
    def __init__(self, items):
        self.items = list(items)

    async def list(self):
        return list(self.items)

    async def add(self, text, category):
        return Invariant(id="new", text=text, category=category)

    async def remove(self, invariant_id):
        pass


GUARD_VIOLATION = (
    '{"violates": true, "invariant_id": "i1", "reason": "просит Node.js"}'
)
GUARD_CLEAN = '{"violates": false}'
INVARIANTS = [Invariant(id="i1", text="Только Python", category="stack")]


def response(text="ok"):
    return LLMResponse(text, "m", TokenUsage(30, 5, 35))


def make_agent(gateway, repository, tasks, invariants):
    return Agent(
        gateway,
        repository=repository,
        counter=TiktokenCounter(),
        config=UsageConfig(),
        candidates_enabled=False,
        task_repository=tasks,
        invariants=invariants,
    )


def chat():
    return Chat(
        id="c1",
        title="T",
        created_at="a",
        updated_at="b",
        messages=[],
        working_memory=WorkingMemory(),
    )


def prompt_text(gateway, index):
    return " ".join(message.content for message in gateway.calls[index])


async def test_violating_request_is_refused_without_content_call():
    gateway = ScriptedGateway([response(GUARD_VIOLATION)])
    tasks = TaskRepository()

    result = await make_agent(
        gateway,
        MemoryRepository(chat()),
        tasks,
        InvariantRepository(INVARIANTS),
    ).run("c1", "Сделай это на Node.js")

    assert len(gateway.calls) == 1
    assert "Только Python" in result.answer
    assert result.violation["invariant_id"] == "i1"
    assert result.violation["invariant"]["text"] == "Только Python"
    assert tasks.state is None


async def test_refusal_does_not_advance_an_existing_task():
    tasks = TaskRepository(TaskState.start("t").accept_plan(["a", "b"]))
    gateway = ScriptedGateway([response(GUARD_VIOLATION)])

    result = await make_agent(
        gateway,
        MemoryRepository(chat()),
        tasks,
        InvariantRepository(INVARIANTS),
    ).run("c1", "перепиши на Rust")

    assert tasks.state.stage == Stage.EXECUTION
    assert tasks.state.step == 0
    assert result.task["step"] == 1
    assert result.violation is not None


async def test_refusal_is_persisted_as_a_message():
    repository = MemoryRepository(chat())
    gateway = ScriptedGateway([response(GUARD_VIOLATION)])

    await make_agent(
        gateway, repository, TaskRepository(), InvariantRepository(INVARIANTS)
    ).run("c1", "на Node.js")

    assert repository.exchanges
    assert "Только Python" in repository.exchanges[0][1]


async def test_clean_request_is_passed_with_invariants_in_prompt():
    gateway = ScriptedGateway(
        [response(GUARD_CLEAN), response('```json\n["шаг"]\n```')]
    )
    tasks = TaskRepository()

    await make_agent(
        gateway,
        MemoryRepository(chat()),
        tasks,
        InvariantRepository(INVARIANTS),
    ).run("c1", "Напиши функцию на Python")

    assert len(gateway.calls) == 2
    assert "Только Python" in prompt_text(gateway, 1)
    assert tasks.state.stage == Stage.EXECUTION


async def test_no_invariants_skips_the_guard_call():
    gateway = ScriptedGateway([response('```json\n["шаг"]\n```')])
    tasks = TaskRepository()

    await make_agent(
        gateway, MemoryRepository(chat()), tasks, InvariantRepository([])
    ).run("c1", "Сделай что-нибудь")

    assert len(gateway.calls) == 1
    assert tasks.state.stage == Stage.EXECUTION
