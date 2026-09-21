import pytest
from fastapi.testclient import TestClient

from app.application.agent import Agent
from app.application.task_engine import APPROVAL_NOTICE, PAUSE_NOTICE
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


def event_response(event, **payload):
    import json

    body = {"event": event, **payload}
    return LLMResponse(
        f"```json\n{json.dumps(body, ensure_ascii=False)}\n```",
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


def propose(client, steps=("Собрать данные", "Написать текст")):
    chat_id = start_chat(client)
    client.gateway.queue.append(plan_response(*steps))
    return chat_id, client.post(
        f"/api/chats/{chat_id}/messages", json={"message": "Сделай отчёт"}
    ).json()


def approve(client):
    return client.post("/api/task/transition", json={"event": "approve_plan"})


def test_state_is_inactive_before_any_task(api):
    state = api.get("/api/task/state").json()

    assert state["active"] is False
    assert state["stage"] is None
    assert state["expected_action"] == DONE_ACTION


def test_transition_table_is_served(api):
    payload = api.get("/api/task/transitions").json()

    stages = [item["key"] for item in payload["stages"]]
    assert stages == [
        "planning",
        "approval",
        "execution",
        "validation",
        "done",
    ]
    approval = next(
        item for item in payload["transitions"] if item["stage"] == "approval"
    )
    assert approval["allowed"] == ["execution"]


def test_first_message_proposes_plan_and_waits(api):
    chat_id, response = propose(api)

    assert response["task"]["stage"] == "approval"
    assert response["task"]["expected_action"].startswith("ожидается")
    state = api.get("/api/task/state").json()
    assert state["active"] is True
    assert state["stage_index"] == 1
    assert state["total_steps"] == 2
    assert state["allowed_stages"] == ["execution"]


def test_approval_blocks_agent_without_calling_gateway(api):
    chat_id, _ = propose(api)
    calls_before = len(api.gateway.calls)

    response = api.post(
        f"/api/chats/{chat_id}/messages", json={"message": "начинай"}
    ).json()

    assert response["answer"] == APPROVAL_NOTICE
    assert len(api.gateway.calls) == calls_before
    assert api.get("/api/task/state").json()["stage"] == "approval"


def test_illegal_transition_is_rejected_and_logged(api):
    propose(api)

    response = api.post(
        "/api/task/transition", json={"event": "complete_step"}
    )

    assert response.status_code == 409
    assert "утвердить план" in response.json()["detail"]["reason"]
    state = api.get("/api/task/state").json()
    assert state["stage"] == "approval"
    assert len(state["rejections"]) == 1
    assert state["rejections"][0]["event"] == "complete_step"


def test_transition_without_active_task_is_rejected(api):
    response = api.post(
        "/api/task/transition", json={"event": "approve_plan"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Нет активной задачи"


def test_propose_plan_without_payload_is_rejected_not_a_crash(api):
    chat_id = start_chat(api)
    api.gateway.queue.append(text_response("без плана"))
    api.gateway.queue.append(text_response("и тут нет"))
    api.post(f"/api/chats/{chat_id}/messages", json={"message": "Задача"})
    assert api.get("/api/task/state").json()["stage"] == "planning"

    response = api.post(
        "/api/task/transition", json={"event": "propose_plan"}
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert isinstance(detail, dict)
    assert "пуст" in detail["reason"].lower()
    assert api.get("/api/task/state").json()["stage"] == "planning"


def test_transition_while_paused_is_rejected(api):
    propose(api)
    api.post("/api/task/pause")

    response = approve(api)

    assert response.status_code == 409
    assert response.json()["detail"] == "Задача на паузе"


def test_pause_blocks_agent_without_calling_gateway(api):
    api.gateway.queue.append(plan_response("Шаг"))
    chat_id = start_chat(api)
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


def test_resume_keeps_approval_then_runs_after_approve(api):
    chat_id, _ = propose(api, ("Первый", "Второй"))
    api.post("/api/task/pause")

    paused = api.get("/api/task/state").json()
    assert paused["paused"] is True
    assert paused["stage"] == "approval"

    resumed = api.post("/api/task/resume").json()
    assert resumed["paused"] is False
    assert resumed["stage"] == "approval"

    approved = approve(api).json()
    assert approved["stage"] == "execution"

    api.gateway.queue.append(event_response("complete_step", result="шаг"))
    response = api.post(
        f"/api/chats/{chat_id}/messages", json={"message": "продолжай"}
    ).json()

    assert response["task"]["stage"] == "execution"
    assert response["task"]["step"] == 2
    block = " ".join(message.content for message in api.gateway.calls[-1])
    assert "не повторяй" in block.lower()


def test_full_flow_reaches_done(api):
    chat_id, _ = propose(api, ("Единственный шаг",))
    approve(api)

    api.gateway.queue.append(event_response("complete_step", result="шаг"))
    after_step = api.post(
        f"/api/chats/{chat_id}/messages", json={"message": "дальше"}
    ).json()
    assert after_step["task"]["stage"] == "validation"

    api.gateway.queue.append(
        event_response("complete_validation", report="отчёт")
    )
    done = api.post(
        f"/api/chats/{chat_id}/messages", json={"message": "проверь"}
    ).json()
    assert done["task"]["stage"] == "done"
    assert done["task"]["paused"] is False
