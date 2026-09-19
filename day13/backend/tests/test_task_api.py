import pytest
from fastapi.testclient import TestClient

from app.application.agent import Agent
from app.application.task_engine import PAUSE_NOTICE
from app.domain.models import LLMResponse, TokenUsage, UsageConfig
from app.domain.task_state import DONE_ACTION
from app.infrastructure.json_memory_repository import JsonMemoryRepository
from app.infrastructure.json_profile_repository import JsonProfileRepository
from app.infrastructure.json_task_repository import JsonTaskRepository
from app.infrastructure.token_counter import TiktokenCounter
from app.main import app
from app.presentation.dependencies import (
    get_agent,
    get_profile_repository,
    get_repository,
    get_task_repository,
    get_usage_config,
)


class QueueGateway:
    def __init__(self):
        self.queue = []
        self.calls = []

    async def complete(self, messages):
        self.calls.append(list(messages))
        if self.queue:
            return self.queue.pop(0)
        return LLMResponse("ok", "m", TokenUsage(30, 5, 35))


def plan_response(*steps):
    import json

    return LLMResponse(
        f"```json\n{json.dumps(list(steps), ensure_ascii=False)}\n```",
        "m",
        TokenUsage(30, 5, 35),
    )


def text_response(text="готово"):
    return LLMResponse(text, "m", TokenUsage(30, 5, 35))


@pytest.fixture
def api(tmp_path):
    memory = JsonMemoryRepository(
        chats_dir=tmp_path / "chats",
        long_term_path=tmp_path / "long_term.json",
        candidates_path=tmp_path / "candidates.json",
    )
    profiles = JsonProfileRepository(profiles_path=tmp_path / "profiles.json")
    tasks = JsonTaskRepository(state_path=tmp_path / "task_state.json")
    gateway = QueueGateway()
    agent = Agent(
        gateway,
        repository=memory,
        counter=TiktokenCounter(),
        config=UsageConfig(),
        candidates_enabled=False,
        profiles=profiles,
        task_repository=tasks,
    )
    app.dependency_overrides[get_repository] = lambda: memory
    app.dependency_overrides[get_profile_repository] = lambda: profiles
    app.dependency_overrides[get_task_repository] = lambda: tasks
    app.dependency_overrides[get_agent] = lambda: agent
    app.dependency_overrides[get_usage_config] = lambda: UsageConfig()
    with TestClient(app) as client:
        client.gateway = gateway
        client.tasks = tasks
        yield client
    app.dependency_overrides.clear()


def start_chat(client) -> str:
    return client.post("/api/chats").json()["id"]


def test_state_is_inactive_before_any_task(api):
    state = api.get("/api/task/state").json()

    assert state["active"] is False
    assert state["stage"] is None
    assert state["expected_action"] == DONE_ACTION


def test_first_message_starts_task_and_returns_state(api):
    chat_id = start_chat(api)
    api.gateway.queue.append(plan_response("Собрать данные", "Написать текст"))

    response = api.post(
        f"/api/chats/{chat_id}/messages", json={"message": "Сделай отчёт"}
    ).json()

    assert response["task"]["stage"] == "execution"
    assert response["task"]["step"] == 1
    state = api.get("/api/task/state").json()
    assert state["active"] is True
    assert state["stage_index"] == 1
    assert state["total_steps"] == 2
    assert state["step_label"] == "Собрать данные"


def test_pause_blocks_agent_without_calling_gateway(api):
    chat_id = start_chat(api)
    api.gateway.queue.append(plan_response("Шаг"))
    api.post(f"/api/chats/{chat_id}/messages", json={"message": "Задача"})
    calls_before = len(api.gateway.calls)

    paused = api.post("/api/task/pause").json()
    assert paused["paused"] is True

    response = api.post(
        f"/api/chats/{chat_id}/messages", json={"message": "ещё"}
    ).json()

    assert response["answer"] == PAUSE_NOTICE
    assert len(api.gateway.calls) == calls_before
    assert api.get("/api/task/state").json()["paused"] is True


def test_resume_continues_without_restarting(api):
    chat_id = start_chat(api)
    api.gateway.queue.append(plan_response("Первый", "Второй"))
    api.post(f"/api/chats/{chat_id}/messages", json={"message": "Задача"})
    api.post("/api/task/pause")
    api.post("/api/task/resume")

    api.gateway.queue.append(text_response("шаг выполнен"))
    response = api.post(
        f"/api/chats/{chat_id}/messages", json={"message": "продолжай"}
    ).json()

    assert response["task"]["stage"] == "execution"
    assert response["task"]["step"] == 2
    block = " ".join(message.content for message in api.gateway.calls[-1])
    assert "не повторяй" in block.lower()


def test_full_flow_reaches_done(api):
    chat_id = start_chat(api)
    api.gateway.queue.append(plan_response("Единственный шаг"))
    api.post(f"/api/chats/{chat_id}/messages", json={"message": "Задача"})

    api.gateway.queue.append(text_response("шаг выполнен"))
    after_step = api.post(
        f"/api/chats/{chat_id}/messages", json={"message": "дальше"}
    ).json()
    assert after_step["task"]["stage"] == "validation"

    api.gateway.queue.append(text_response("отчёт проверки"))
    done = api.post(
        f"/api/chats/{chat_id}/messages", json={"message": "проверь"}
    ).json()
    assert done["task"]["stage"] == "done"
    assert done["task"]["paused"] is False
