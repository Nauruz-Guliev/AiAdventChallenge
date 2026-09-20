from app.application.agent import Agent
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

    async def get_chat(self, chat_id):
        return self.chat

    async def get_long_term(self):
        return LongTermMemory()

    async def append_exchange(self, chat_id, user, assistant, usage, used=None):
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


def response(text="ok"):
    return LLMResponse(text, "m", TokenUsage(30, 5, 35))


def make_agent(gateway, repository, tasks):
    return Agent(
        gateway,
        repository=repository,
        counter=TiktokenCounter(),
        config=UsageConfig(),
        candidates_enabled=False,
        task_repository=tasks,
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


def prompt_text(gateway, index=0):
    return " ".join(message.content for message in gateway.calls[index])


async def test_first_message_starts_planning_and_accepts_the_plan():
    gateway = ScriptedGateway(
        [response('```json\n["Собрать данные", "Написать текст"]\n```')]
    )
    tasks = TaskRepository()

    result = await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "Сделай отчёт"
    )

    first_prompt = prompt_text(gateway)
    assert "планирование" in first_prompt.lower()
    assert "json" in first_prompt.lower()
    assert tasks.state.stage == Stage.EXECUTION
    assert tasks.state.steps == ("Собрать данные", "Написать текст")
    assert result.task["stage"] == "execution"
    assert result.task["step"] == 1
    assert result.answer.startswith("План работы")
    assert "1. Собрать данные" in result.answer
    assert "```" not in result.answer


async def test_plan_failure_is_retried_once_and_accepted():
    gateway = ScriptedGateway([response("без плана"), response('```json\n["a"]\n```')])
    tasks = TaskRepository()

    await make_agent(gateway, MemoryRepository(chat()), tasks).run("c1", "t")

    assert len(gateway.calls) == 2
    assert tasks.state.stage == Stage.EXECUTION


async def test_plan_failure_twice_keeps_planning():
    gateway = ScriptedGateway([response("без плана"), response("и тут нет")])
    tasks = TaskRepository()

    await make_agent(gateway, MemoryRepository(chat()), tasks).run("c1", "t")

    assert len(gateway.calls) == 2
    assert tasks.state.stage == Stage.PLANNING


async def test_execution_step_advances_and_prompt_forbids_repeats():
    tasks = TaskRepository(TaskState.start("t").accept_plan(["a", "b"]))
    gateway = ScriptedGateway([response("шаг сделан")])

    result = await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "продолжай"
    )

    block = prompt_text(gateway)
    assert "шаг 1 из 2" in block.lower()
    assert "не повторяй" in block.lower()
    assert tasks.state.stage == Stage.EXECUTION
    assert result.task["step"] == 2


async def test_last_step_moves_to_validation():
    tasks = TaskRepository(
        TaskState.start("t").accept_plan(["a", "b"]).advance_step()
    )
    gateway = ScriptedGateway([response("шаг сделан")])

    await make_agent(gateway, MemoryRepository(chat()), tasks).run("c1", "дальше")

    assert tasks.state.stage == Stage.VALIDATION


async def test_validation_finishes_the_task():
    tasks = TaskRepository(
        TaskState.start("t").accept_plan(["a"]).advance_step()
    )
    gateway = ScriptedGateway([response("отчёт проверки")])

    result = await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "проверь"
    )

    assert tasks.state.stage == Stage.DONE
    assert result.task["stage"] == "done"


async def test_message_after_done_starts_a_new_task():
    tasks = TaskRepository(
        TaskState.start("старая задача").accept_plan(["a"]).advance_step().finish()
    )
    gateway = ScriptedGateway([response('```json\n["новый шаг"]\n```')])

    await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "Новая задача"
    )

    assert tasks.state.stage == Stage.EXECUTION
    assert tasks.state.task == "Новая задача"
