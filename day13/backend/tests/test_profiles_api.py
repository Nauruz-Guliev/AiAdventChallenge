import pytest
from fastapi.testclient import TestClient

from app.domain.models import UsageConfig
from app.infrastructure.json_memory_repository import JsonMemoryRepository
from app.infrastructure.json_profile_repository import JsonProfileRepository
from app.main import app
from app.presentation.dependencies import (
    get_agent,
    get_profile_repository,
    get_repository,
    get_usage_config,
)


class FakeAgent:
    async def run(self, chat_id, message):
        raise AssertionError("agent must not be called in profile API tests")


@pytest.fixture
def client(tmp_path):
    memory = JsonMemoryRepository(
        chats_dir=tmp_path / "chats",
        long_term_path=tmp_path / "long_term.json",
        candidates_path=tmp_path / "candidates.json",
    )
    profiles = JsonProfileRepository(profiles_path=tmp_path / "profiles.json")
    app.dependency_overrides[get_repository] = lambda: memory
    app.dependency_overrides[get_profile_repository] = lambda: profiles
    app.dependency_overrides[get_agent] = lambda: FakeAgent()
    app.dependency_overrides[get_usage_config] = lambda: UsageConfig()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_store_is_seeded_and_active_is_business(client):
    store = client.get("/api/profiles").json()

    assert [item["title"] for item in store["profiles"]] == [
        "Нейтральный (без персонализации)",
        "Деловой",
        "Коротко и по делу",
        "Наставник",
    ]
    assert client.get("/api/profile").json()["title"] == "Деловой"


def test_presets_endpoint(client):
    presets = client.get("/api/profiles/presets").json()
    assert [item["key"] for item in presets] == [
        "neutral",
        "business",
        "concise",
        "mentor",
    ]


def test_create_from_preset_activate_and_update(client):
    created = client.post("/api/profiles/from-preset", json={"key": "concise"})
    assert created.status_code == 201
    profile_id = created.json()["id"]

    assert client.post(f"/api/profiles/{profile_id}/activate").status_code == 200
    assert client.get("/api/profile").json()["title"] == "Коротко и по делу"

    updated = client.put(
        f"/api/profiles/{profile_id}",
        json={"tone": "friendly", "constraints": ["без эмодзи"]},
    )
    assert updated.status_code == 200
    assert updated.json()["tone"] == "friendly"
    assert updated.json()["constraints"] == ["без эмодзи"]


def test_create_custom_profile_and_validation(client):
    created = client.post(
        "/api/profiles",
        json={
            "title": "Свой",
            "tone": "formal",
            "length": "short",
            "structure": "bullets",
        },
    )
    assert created.status_code == 201
    assert created.json()["title"] == "Свой"

    bad = client.post("/api/profiles", json={"title": "X", "tone": "nonsense"})
    assert bad.status_code == 422

    too_many = client.post(
        "/api/profiles",
        json={"title": "X", "constraints": [f"c{i}" for i in range(25)]},
    )
    assert too_many.status_code == 400


def test_cannot_delete_last_profile_and_404(client):
    store = client.get("/api/profiles").json()
    ids = [item["id"] for item in store["profiles"]]
    for profile_id in ids[1:]:
        assert client.delete(f"/api/profiles/{profile_id}").status_code == 204
    assert client.delete(f"/api/profiles/{ids[0]}").status_code == 400
    assert client.delete("/api/profiles/missing").status_code == 404


def test_update_title_is_validated(client):
    store = client.get("/api/profiles").json()
    profile_id = store["profiles"][0]["id"]

    blank = client.put(f"/api/profiles/{profile_id}", json={"title": "   "})
    assert blank.status_code == 400

    too_long = client.put(
        f"/api/profiles/{profile_id}", json={"title": "x" * 61}
    )
    assert too_long.status_code == 400
