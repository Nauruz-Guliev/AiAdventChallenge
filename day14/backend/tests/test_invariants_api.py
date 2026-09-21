import pytest
from fastapi.testclient import TestClient

from app.domain.models import UsageConfig
from app.infrastructure.json_invariant_repository import (
    JsonInvariantRepository,
)
from app.infrastructure.json_memory_repository import JsonMemoryRepository
from app.infrastructure.json_profile_repository import JsonProfileRepository
from app.infrastructure.json_task_repository import JsonTaskRepository
from app.main import app
from app.presentation.dependencies import (
    get_agent,
    get_invariant_repository,
    get_profile_repository,
    get_repository,
    get_task_repository,
    get_usage_config,
)


class FakeAgent:
    async def run(self, chat_id, message):
        raise AssertionError("agent must not be called in invariant API tests")


@pytest.fixture
def client(tmp_path):
    memory = JsonMemoryRepository(
        chats_dir=tmp_path / "chats",
        long_term_path=tmp_path / "long_term.json",
        candidates_path=tmp_path / "candidates.json",
    )
    profiles = JsonProfileRepository(profiles_path=tmp_path / "profiles.json")
    invariants = JsonInvariantRepository(path=tmp_path / "invariants.json")
    app.dependency_overrides[get_repository] = lambda: memory
    app.dependency_overrides[get_profile_repository] = lambda: profiles
    app.dependency_overrides[get_invariant_repository] = lambda: invariants
    app.dependency_overrides[get_agent] = lambda: FakeAgent()
    app.dependency_overrides[get_task_repository] = lambda: JsonTaskRepository(
        state_path=tmp_path / "task_state.json"
    )
    app.dependency_overrides[get_usage_config] = lambda: UsageConfig()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_seeded_invariants_cover_all_categories(client):
    items = client.get("/api/invariants").json()

    assert len(items) >= 4
    assert {item["category"] for item in items} >= {
        "architecture",
        "stack",
        "decision",
        "business",
    }
    assert all(item["id"] and item["text"] for item in items)


def test_create_and_delete_invariant(client):
    created = client.post(
        "/api/invariants", json={"text": "Только Python", "category": "stack"}
    )

    assert created.status_code == 201
    body = created.json()
    assert body["text"] == "Только Python"
    assert body["category"] == "stack"

    assert client.delete(f"/api/invariants/{body['id']}").status_code == 204
    remaining = client.get("/api/invariants").json()
    assert all(item["id"] != body["id"] for item in remaining)


def test_create_validates_input(client):
    blank = client.post(
        "/api/invariants", json={"text": "   ", "category": "stack"}
    )
    bad_category = client.post(
        "/api/invariants", json={"text": "ok", "category": "nonsense"}
    )

    assert blank.status_code == 422
    assert bad_category.status_code == 422


def test_delete_unknown_returns_404(client):
    assert client.delete("/api/invariants/missing").status_code == 404
