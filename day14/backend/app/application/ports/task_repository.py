from typing import Protocol

from app.domain.task_state import TaskState


class TaskRepository(Protocol):
    async def get(self) -> TaskState | None:
        ...

    async def save(self, state: TaskState) -> None:
        ...
