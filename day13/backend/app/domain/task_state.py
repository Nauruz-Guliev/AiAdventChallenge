from dataclasses import dataclass, replace
from enum import Enum


class InvalidTransitionError(Exception):
    """Raised when a state machine transition is not allowed."""


class Stage(str, Enum):
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    DONE = "done"


STAGE_ORDER = (Stage.PLANNING, Stage.EXECUTION, Stage.VALIDATION, Stage.DONE)

STAGE_LABELS = {
    Stage.PLANNING: "планирование",
    Stage.EXECUTION: "выполнение",
    Stage.VALIDATION: "проверка",
    Stage.DONE: "готово",
}

STAGES = [
    {"key": stage.value, "label": STAGE_LABELS[stage]} for stage in STAGE_ORDER
]

PLANNING_ACTION = "ожидается: агент составляет план"
VALIDATION_ACTION = "ожидается: агент проверяет результат"
DONE_ACTION = "ожидается: новая задача от пользователя"
PAUSED_ACTION = "ожидается: пользователь нажмёт «Продолжить»"


@dataclass(frozen=True)
class TaskState:
    """Finite state machine state of the single active task.

    ``step`` is a zero-based index of the current execution step.
    Pause is an orthogonal flag: it can be set on any stage except ``DONE``.
    """

    task: str
    stage: Stage
    step: int = 0
    steps: tuple[str, ...] = ()
    paused: bool = False

    @staticmethod
    def start(task: str) -> "TaskState":
        return TaskState(task=task, stage=Stage.PLANNING)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def step_number(self) -> int:
        if self.stage == Stage.PLANNING:
            return 0
        if self.stage == Stage.EXECUTION:
            return self.step + 1
        return self.total_steps

    @property
    def step_label(self) -> str | None:
        if self.stage == Stage.EXECUTION and self.steps:
            return self.steps[self.step]
        return None

    @property
    def expected_action(self) -> str:
        if self.paused:
            return PAUSED_ACTION
        if self.stage == Stage.PLANNING:
            return PLANNING_ACTION
        if self.stage == Stage.EXECUTION:
            return f"ожидается: агент выполняет шаг {self.step + 1}"
        if self.stage == Stage.VALIDATION:
            return VALIDATION_ACTION
        return DONE_ACTION

    def accept_plan(self, steps: tuple[str, ...] | list[str]) -> "TaskState":
        if self.stage != Stage.PLANNING:
            raise InvalidTransitionError(
                f"План нельзя принять на этапе {self.stage.value}"
            )
        normalized = tuple(item.strip() for item in steps if item.strip())
        if not normalized:
            raise ValueError("План не может быть пустым")
        return replace(
            self, stage=Stage.EXECUTION, step=0, steps=normalized
        )

    def advance_step(self) -> "TaskState":
        if self.stage != Stage.EXECUTION:
            raise InvalidTransitionError(
                f"Шаг нельзя продвинуть на этапе {self.stage.value}"
            )
        next_index = self.step + 1
        if next_index >= self.total_steps:
            return replace(self, stage=Stage.VALIDATION, step=self.total_steps)
        return replace(self, step=next_index)

    def finish(self) -> "TaskState":
        if self.stage != Stage.VALIDATION:
            raise InvalidTransitionError(
                f"Завершить задачу нельзя на этапе {self.stage.value}"
            )
        return replace(self, stage=Stage.DONE, paused=False)

    def pause(self) -> "TaskState":
        if self.stage == Stage.DONE:
            return self
        return replace(self, paused=True)

    def resume(self) -> "TaskState":
        return replace(self, paused=False)

    def to_dict(self) -> dict:
        return {
            "active": True,
            "task": self.task,
            "stage": self.stage.value,
            "stage_index": STAGE_ORDER.index(self.stage),
            "step": self.step_number,
            "step_index": self.step,
            "total_steps": self.total_steps,
            "step_label": self.step_label,
            "expected_action": self.expected_action,
            "paused": self.paused,
            "steps": list(self.steps),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TaskState":
        return cls(
            task=payload["task"],
            stage=Stage(payload["stage"]),
            step=int(payload.get("step_index", payload.get("step", 0))),
            steps=tuple(payload.get("steps", ())),
            paused=bool(payload.get("paused", False)),
        )
