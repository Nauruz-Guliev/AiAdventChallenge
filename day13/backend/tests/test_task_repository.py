from pathlib import Path

from app.domain.task_state import Stage, TaskState
from app.infrastructure.json_task_repository import JsonTaskRepository


def repository(tmp_path: Path) -> JsonTaskRepository:
    return JsonTaskRepository(state_path=tmp_path / "task_state.json")


async def test_missing_file_returns_none(tmp_path):
    assert await repository(tmp_path).get() is None


async def test_save_and_get_roundtrip(tmp_path):
    repo = repository(tmp_path)
    state = TaskState.start("сделай X").accept_plan(["a", "b"]).advance_step()

    await repo.save(state)

    assert await repo.get() == state


async def test_corrupt_file_returns_none(tmp_path):
    path = tmp_path / "task_state.json"
    path.write_text("{not json", encoding="utf-8")

    assert await repository(tmp_path).get() is None


async def test_unknown_stage_returns_none(tmp_path):
    path = tmp_path / "task_state.json"
    path.write_text(
        '{"version": 1, "state": {"task": "t", "stage": "nonsense"}}',
        encoding="utf-8",
    )

    assert await repository(tmp_path).get() is None


async def test_saved_state_keeps_pause_and_stage(tmp_path):
    repo = repository(tmp_path)
    await repo.save(TaskState.start("t").accept_plan(["a"]).pause())

    state = await repo.get()

    assert state.stage == Stage.EXECUTION
    assert state.paused is True
