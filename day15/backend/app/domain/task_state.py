from dataclasses import asdict, dataclass, replace
from enum import Enum

REJECTION_LIMIT = 5


class InvalidTransitionError(Exception):
    """Raised when a state machine transition is not allowed."""

    def __init__(self, event: str, state: "TaskState") -> None:
        self.event = str(event)
        self.from_stage = state.stage
        super().__init__(
            f"Переход «{self.event}» недопустим на этапе «{state.stage.value}»"
        )


class Stage(str, Enum):
    PLANNING = "planning"
    APPROVAL = "approval"
    EXECUTION = "execution"
    VALIDATION = "validation"
    DONE = "done"


class Event(str, Enum):
    PROPOSE_PLAN = "propose_plan"
    APPROVE_PLAN = "approve_plan"
    COMPLETE_STEP = "complete_step"
    COMPLETE_VALIDATION = "complete_validation"


STAGE_ORDER = (
    Stage.PLANNING,
    Stage.APPROVAL,
    Stage.EXECUTION,
    Stage.VALIDATION,
    Stage.DONE,
)

STAGE_LABELS = {
    Stage.PLANNING: "планирование",
    Stage.APPROVAL: "утверждение плана",
    Stage.EXECUTION: "выполнение",
    Stage.VALIDATION: "проверка",
    Stage.DONE: "готово",
}

ALLOWED_TRANSITIONS = {
    Stage.PLANNING: (Stage.APPROVAL,),
    Stage.APPROVAL: (Stage.EXECUTION,),
    Stage.EXECUTION: (Stage.EXECUTION, Stage.VALIDATION),
    Stage.VALIDATION: (Stage.DONE,),
    Stage.DONE: (),
}

EVENT_STAGE = {
    Event.PROPOSE_PLAN: Stage.PLANNING,
    Event.APPROVE_PLAN: Stage.APPROVAL,
    Event.COMPLETE_STEP: Stage.EXECUTION,
    Event.COMPLETE_VALIDATION: Stage.VALIDATION,
}

EVENT_LABELS = {
    Event.PROPOSE_PLAN: "предложить план",
    Event.APPROVE_PLAN: "утвердить план",
    Event.COMPLETE_STEP: "завершить шаг",
    Event.COMPLETE_VALIDATION: "завершить проверку",
}

STAGE_REQUIREMENT = {
    Stage.PLANNING: "сначала ассистент должен предложить план",
    Stage.APPROVAL: "сначала нужно утвердить план",
    Stage.EXECUTION: "сначала нужно завершить текущий шаг",
    Stage.VALIDATION: "сначала нужно провести проверку",
    Stage.DONE: "нужна новая задача",
}

STAGES = [
    {"key": stage.value, "label": STAGE_LABELS[stage]} for stage in STAGE_ORDER
]

PLANNING_ACTION = "ожидается: агент предложит план"
APPROVAL_ACTION = "ожидается: пользователь утвердит план"
VALIDATION_ACTION = "ожидается: агент проверяет результат"
DONE_ACTION = "ожидается: новая задача от пользователя"
PAUSED_ACTION = "ожидается: пользователь нажмёт «Продолжить»"


@dataclass(frozen=True)
class TransitionRejection:
    """A transition the assistant asked for but the table did not allow."""

    event: str
    from_stage: str
    to_stage: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "TransitionRejection":
        return cls(
            event=payload["event"],
            from_stage=payload["from_stage"],
            to_stage=payload.get("to_stage", ""),
            reason=payload["reason"],
        )


@dataclass(frozen=True)
class TaskState:
    """Finite state machine state of the single active task.

    ``step`` is a zero-based index of the current execution step. Pause is an
    orthogonal flag: it can be set on any stage except ``DONE``. ``rejections``
    keeps the most recent refused transitions so the UI can explain them.
    """

    task: str
    stage: Stage
    step: int = 0
    steps: tuple[str, ...] = ()
    paused: bool = False
    rejections: tuple[TransitionRejection, ...] = ()

    @staticmethod
    def start(task: str) -> "TaskState":
        return TaskState(task=task, stage=Stage.PLANNING)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def step_number(self) -> int:
        if self.stage in (Stage.PLANNING, Stage.APPROVAL):
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
    def allowed_stages(self) -> tuple[Stage, ...]:
        return ALLOWED_TRANSITIONS[self.stage]

    @property
    def expected_action(self) -> str:
        if self.paused:
            return PAUSED_ACTION
        if self.stage == Stage.PLANNING:
            return PLANNING_ACTION
        if self.stage == Stage.APPROVAL:
            return APPROVAL_ACTION
        if self.stage == Stage.EXECUTION:
            return f"ожидается: агент выполняет шаг {self.step + 1}"
        if self.stage == Stage.VALIDATION:
            return VALIDATION_ACTION
        return DONE_ACTION

    def propose_plan(self, steps: tuple[str, ...] | list[str]) -> "TaskState":
        if self.stage != Stage.PLANNING:
            raise InvalidTransitionError(Event.PROPOSE_PLAN, self)
        normalized = tuple(item.strip() for item in steps if item.strip())
        if not normalized:
            raise ValueError("План не может быть пустым")
        return replace(
            self, stage=Stage.APPROVAL, step=0, steps=normalized
        )

    def approve_plan(self) -> "TaskState":
        if self.stage != Stage.APPROVAL:
            raise InvalidTransitionError(Event.APPROVE_PLAN, self)
        return replace(self, stage=Stage.EXECUTION, step=0)

    def complete_step(self) -> "TaskState":
        if self.stage != Stage.EXECUTION:
            raise InvalidTransitionError(Event.COMPLETE_STEP, self)
        next_index = self.step + 1
        if next_index >= self.total_steps:
            return replace(self, stage=Stage.VALIDATION, step=self.total_steps)
        return replace(self, step=next_index)

    def complete_validation(self) -> "TaskState":
        if self.stage != Stage.VALIDATION:
            raise InvalidTransitionError(Event.COMPLETE_VALIDATION, self)
        return replace(self, stage=Stage.DONE, paused=False)

    def pause(self) -> "TaskState":
        if self.stage == Stage.DONE:
            return self
        return replace(self, paused=True)

    def resume(self) -> "TaskState":
        return replace(self, paused=False)

    def record_rejection(
        self, rejection: TransitionRejection
    ) -> "TaskState":
        keep = (*self.rejections, rejection)[-REJECTION_LIMIT:]
        return replace(self, rejections=keep)

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
            "allowed_stages": [stage.value for stage in self.allowed_stages],
            "rejections": [
                rejection.to_dict() for rejection in self.rejections
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TaskState":
        return cls(
            task=payload["task"],
            stage=Stage(payload["stage"]),
            step=int(payload.get("step_index", payload.get("step", 0))),
            steps=tuple(payload.get("steps", ())),
            paused=bool(payload.get("paused", False)),
            rejections=tuple(
                TransitionRejection.from_dict(item)
                for item in payload.get("rejections", ())
            ),
        )


def _to_event(event: Event | str) -> Event | None:
    if isinstance(event, Event):
        return event
    try:
        return Event(str(event))
    except ValueError:
        return None


def _rejection(
    state: TaskState, event: Event | str, error: str | None = None
) -> TransitionRejection:
    known = _to_event(event)
    name = known.value if known is not None else str(event)
    if error is not None:
        reason = f"Некорректный запрос перехода «{name}»: {error}."
    elif known is not None:
        reason = (
            f"Действие «{EVENT_LABELS[known]}» недоступно на этапе "
            f"«{STAGE_LABELS[state.stage]}»: {STAGE_REQUIREMENT[state.stage]}."
        )
    else:
        reason = (
            f"Неизвестное действие «{event}» на этапе "
            f"«{STAGE_LABELS[state.stage]}»."
        )
    return TransitionRejection(
        event=name,
        from_stage=state.stage.value,
        to_stage=EVENT_STAGE[known].value if known is not None else "",
        reason=reason,
    )


def transition(
    state: TaskState, event: Event | str, steps: list[str] | tuple[str, ...] | None = None
) -> TaskState:
    """Apply the single allowed transition for ``event`` or raise."""
    known = _to_event(event)
    if known is None:
        raise InvalidTransitionError(event, state)
    if known == Event.PROPOSE_PLAN:
        return state.propose_plan(steps or ())
    if known == Event.APPROVE_PLAN:
        return state.approve_plan()
    if known == Event.COMPLETE_STEP:
        return state.complete_step()
    return state.complete_validation()


def attempt(
    state: TaskState,
    event: Event | str,
    steps: list[str] | tuple[str, ...] | None = None,
) -> tuple[TaskState, TransitionRejection | None]:
    """Try a transition; on refusal keep the state and log the attempt."""
    try:
        new_state = transition(state, event, steps=steps)
    except InvalidTransitionError:
        rejection = _rejection(state, event)
    except ValueError as error:
        rejection = _rejection(state, event, error=str(error))
    else:
        return new_state, None
    return state.record_rejection(rejection), rejection
