import pytest

from app.domain.models import (
    ProfileConflict,
    ProfileNotFound,
    UserProfile,
)
from app.infrastructure.json_profile_repository import JsonProfileRepository


def repo(tmp_path):
    return JsonProfileRepository(profiles_path=tmp_path / "profiles.json")


async def test_first_read_seeds_presets_with_business_active(tmp_path):
    store = await repo(tmp_path).get_store()

    titles = [item.title for item in store.profiles]
    assert titles == [
        "Нейтральный (без персонализации)",
        "Деловой",
        "Коротко и по делу",
        "Наставник",
    ]
    assert store.active().title == "Деловой"
    assert (tmp_path / "profiles.json").exists()


async def test_create_update_and_activate(tmp_path):
    repository = repo(tmp_path)
    created = await repository.create(UserProfile(id="p-custom", title="Свой"))
    updated = await repository.update("p-custom", {"tone": "friendly"})

    assert created.id == "p-custom"
    assert updated.tone == "friendly"
    activated = await repository.activate("p-custom")
    assert activated.id == "p-custom"
    assert (await repository.get_active()).id == "p-custom"


async def test_update_missing_profile_raises(tmp_path):
    with pytest.raises(ProfileNotFound):
        await repo(tmp_path).update("missing", {"tone": "formal"})


async def test_cannot_delete_last_profile(tmp_path):
    repository = repo(tmp_path)
    store = await repository.get_store()
    keeper = store.profiles[0]
    for item in store.profiles[1:]:
        await repository.delete(item.id)

    with pytest.raises(ProfileConflict):
        await repository.delete(keeper.id)


async def test_deleting_active_switches_to_first_remaining(tmp_path):
    repository = repo(tmp_path)
    store = await repository.get_store()
    active_id = store.active_id

    await repository.delete(active_id)

    assert (await repository.get_active()).id != active_id
    assert len((await repository.get_store()).profiles) == 3
