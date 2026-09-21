import pytest

from app.domain.invariant import (
    INVARIANT_CATEGORIES,
    InvariantNotFound,
)
from app.infrastructure.json_invariant_repository import JsonInvariantRepository


def repository(tmp_path):
    return JsonInvariantRepository(path=tmp_path / "invariants.json")


async def test_empty_store_is_seeded(tmp_path):
    items = await repository(tmp_path).list()

    assert items
    assert all(item.text for item in items)
    assert all(item.category in INVARIANT_CATEGORIES for item in items)


async def test_seed_is_persisted_and_stable(tmp_path):
    first = await repository(tmp_path).list()
    second = await repository(tmp_path).list()

    assert [item.id for item in first] == [item.id for item in second]
    assert (tmp_path / "invariants.json").exists()


async def test_add_and_remove(tmp_path):
    repo = repository(tmp_path)

    created = await repo.add("  Только Python  ", "stack")

    assert created.text == "Только Python"
    assert created.category == "stack"
    assert any(item.id == created.id for item in await repo.list())

    await repo.remove(created.id)
    assert all(item.id != created.id for item in await repo.list())


async def test_add_rejects_blank_text_and_unknown_category(tmp_path):
    repo = repository(tmp_path)

    with pytest.raises(ValueError):
        await repo.add("   ", "stack")
    with pytest.raises(ValueError):
        await repo.add("текст", "nonsense")


async def test_remove_unknown_raises(tmp_path):
    with pytest.raises(InvariantNotFound):
        await repository(tmp_path).remove("missing")


async def test_invariants_live_in_their_own_file(tmp_path):
    await repository(tmp_path).add("правило", "business")

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "invariants.json"
    ]


async def test_removing_all_invariants_is_not_reseeded(tmp_path):
    repo = repository(tmp_path)
    for item in await repo.list():
        await repo.remove(item.id)

    assert await repo.list() == []
