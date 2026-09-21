import asyncio
from pathlib import Path

from app.domain.models import ChatPersistenceError
from app.domain.task_state import TaskState
from app.infrastructure.json_store import read_json_object, write_json_object


class JsonTaskRepository:
    def __init__(self, state_path: Path):
        self._state_path = state_path
        self._lock = asyncio.Lock()

    async def get(self) -> TaskState | None:
        async with self._lock:
            return self._read_state()

    async def save(self, state: TaskState) -> None:
        async with self._lock:
            write_json_object(
                self._state_path,
                {"version": 1, "state": state.to_dict()},
            )

    def _read_state(self) -> TaskState | None:
        if not self._state_path.exists():
            return None
        try:
            payload = read_json_object(self._state_path)
            state_payload = payload.get("state")
            if not isinstance(state_payload, dict):
                return None
            return TaskState.from_dict(state_payload)
        except (ChatPersistenceError, KeyError, ValueError):
            return None
