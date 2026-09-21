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


def envelope(event, **payload):
    import json

    body = {"event": event, **payload}
    return response(f"```json\n{json.dumps(body, ensure_ascii=False)}\n```")


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


def running():
    return TaskState.start("t").propose_plan(["a", "b"]).approve_plan()


async def test_first_message_proposes_plan_and_waits_for_approval():
    gateway = ScriptedGateway(
        [response('```json\n["Собрать данные", "Написать текст"]\n```')]
    )
    tasks = TaskRepository()

    result = await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "Сделай отчёт"
    )

    first_prompt = prompt_text(gateway)
    assert "планирование" in first_prompt.lower()
    assert "propose_plan" in first_prompt
    assert tasks.state.stage == Stage.APPROVAL
    assert tasks.state.steps == ("Собрать данные", "Написать текст")
    assert result.task["stage"] == "approval"
    assert result.answer.startswith("План работы")
    assert "1. Собрать данные" in result.answer
    assert "```" not in result.answer


async def test_plan_failure_is_retried_once_and_accepted():
    gateway = ScriptedGateway(
        [response("без плана"), response('```json\n["a"]\n```')]
    )
    tasks = TaskRepository()

    await make_agent(gateway, MemoryRepository(chat()), tasks).run("c1", "t")

    assert len(gateway.calls) == 2
    assert tasks.state.stage == Stage.APPROVAL


async def test_plan_failure_twice_keeps_planning():
    gateway = ScriptedGateway([response("без плана"), response("и тут нет")])
    tasks = TaskRepository()

    await make_agent(gateway, MemoryRepository(chat()), tasks).run("c1", "t")

    assert len(gateway.calls) == 2
    assert tasks.state.stage == Stage.PLANNING


async def test_execution_step_advances_and_prompt_forbids_repeats():
    tasks = TaskRepository(running())
    gateway = ScriptedGateway([envelope("complete_step", result="шаг сделан")])

    result = await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "продолжай"
    )

    block = prompt_text(gateway)
    assert "шаг 1 из 2" in block.lower()
    assert "не повторяй" in block.lower()
    assert "complete_step" in block
    assert tasks.state.stage == Stage.EXECUTION
    assert result.task["step"] == 2
    assert result.answer == "шаг сделан"


async def test_last_step_moves_to_validation():
    tasks = TaskRepository(
        running().complete_step()
    )
    gateway = ScriptedGateway([envelope("complete_step", result="готово")])

    await make_agent(gateway, MemoryRepository(chat()), tasks).run("c1", "дальше")

    assert tasks.state.stage == Stage.VALIDATION


async def test_validation_finishes_the_task():
    tasks = TaskRepository(running().complete_step().complete_step())
    gateway = ScriptedGateway(
        [envelope("complete_validation", report="отчёт проверки")]
    )

    result = await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "проверь"
    )

    assert tasks.state.stage == Stage.DONE
    assert result.task["stage"] == "done"
    assert result.answer == "отчёт проверки"


async def test_assistant_cannot_jump_to_done_from_execution():
    tasks = TaskRepository(running())
    gateway = ScriptedGateway(
        [envelope("complete_validation", report="сразу финал")]
    )

    result = await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "заканчивай"
    )

    assert tasks.state.stage == Stage.EXECUTION
    assert len(tasks.state.rejections) == 1
    assert result.answer.startswith("⚠")
    assert "недоступно" in result.answer
    assert "сразу финал" in result.answer
    assert "```" not in result.answer
    assert result.task["rejections"][0]["event"] == "complete_validation"


async def test_assistant_cannot_jump_past_planning():
    tasks = TaskRepository()
    gateway = ScriptedGateway(
        [envelope("complete_step", result="сразу делаю")]
    )

    result = await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "Сделай отчёт"
    )

    assert len(gateway.calls) == 1
    assert tasks.state.stage == Stage.PLANNING
    assert len(tasks.state.rejections) == 1
    assert result.answer.startswith("⚠")
    assert "сразу делаю" in result.answer


async def test_message_after_done_starts_a_new_task():
    tasks = TaskRepository(
        running().complete_step().complete_step().complete_validation()
    )
    gateway = ScriptedGateway([response('```json\n["новый шаг"]\n```')])

    await make_agent(gateway, MemoryRepository(chat()), tasks).run(
        "c1", "Новая задача"
    )

    assert tasks.state.stage == Stage.APPROVAL
    assert tasks.state.task == "Новая задача"
