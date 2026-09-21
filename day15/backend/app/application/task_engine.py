import json
import re
from dataclasses import dataclass

from app.domain.task_state import (
    STAGE_LABELS,
    Event,
    Stage,
    TaskState,
    TransitionRejection,
)

PAUSE_NOTICE = (
    "Задача на паузе. Нажмите «Продолжить», чтобы агент вернулся к работе."
)
APPROVAL_NOTICE = (
    "План предложен и ждёт утверждения. Нажмите «Утвердить план», "
    "чтобы начать выполнение."
)
PLAN_FORMAT_HINT = (
    "Ответ не содержал корректный план. Верни СТРОГО один JSON-объект "
    '{"event": "propose_plan", "steps": ["шаг 1", "шаг 2", "шаг 3"]} '
    "в блоке ```json ... ``` и без другого текста."
)

_FENCED = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$")
_BODY_KEYS = ("result", "report", "summary", "text", "answer", "content")


@dataclass(frozen=True)
class Proposal:
    """A transition the assistant asked for, plus its human-readable body."""

    event: str
    text: str
    steps: tuple[str, ...] | None = None


def parse_plan(text: str) -> tuple[str, ...] | None:
    for candidate in _plan_candidates(text):
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, list):
            continue
        steps = tuple(
            item.strip()
            for item in payload
            if isinstance(item, str) and item.strip()
        )
        if steps:
            return steps
    return _numbered_steps(text) or None


def parse_proposal(text: str, expected: Event) -> Proposal:
    payload = _first_object(text)
    if payload is not None and isinstance(payload.get("event"), str):
        return Proposal(
            event=payload["event"].strip(),
            text=_body(payload) or text,
            steps=_steps(payload),
        )
    if expected == Event.PROPOSE_PLAN:
        return Proposal(
            event=expected.value, text=text, steps=parse_plan(text)
        )
    return Proposal(event=expected.value, text=text)


def build_rejection_notice(
    rejection: TransitionRejection, state: TaskState
) -> str:
    return (
        f"⚠ {rejection.reason} Задача осталась на этапе "
        f"«{STAGE_LABELS[state.stage]}»."
    )


def render_plan(steps: tuple[str, ...] | list[str]) -> str:
    items = list(steps)
    lines = "\n".join(
        f"{index}. {step}" for index, step in enumerate(items, 1)
    )
    return f"План работы ({len(items)} шагов):\n{lines}"


def build_task_block(state: TaskState) -> str:
    lines = ["## Состояние задачи", f"Этап: {STAGE_LABELS[state.stage]}"]
    if state.stage == Stage.PLANNING:
        lines += [
            f"Задача пользователя: {state.task}",
            "Составь план выполнения задачи из 3–6 шагов.",
            "Ответь СТРОГО одним JSON-объектом в блоке ```json ... ``` вида "
            '{"event": "propose_plan", "steps": ["шаг 1", "шаг 2", "шаг 3"]} '
            "и больше ничем. Не начинай выполнение до утверждения плана.",
        ]
    elif state.stage == Stage.APPROVAL:
        lines += [
            f"Задача: {state.task}",
            "Предложенный план:",
            *[f"{index}. {step}" for index, step in enumerate(state.steps, 1)],
            "Реализация начнётся только после утверждения плана "
            "пользователем. Дождись утверждения.",
        ]
    elif state.stage == Stage.EXECUTION:
        lines += [
            f"Задача: {state.task}",
            f"Шаг {state.step + 1} из {state.total_steps}: {state.step_label}",
            "Выполни только этот шаг. Не повторяй план и предыдущие "
            "объяснения.",
            "Ответь СТРОГО одним JSON-объектом в блоке ```json ... ``` вида "
            '{"event": "complete_step", "result": "результат шага"} '
            "и больше ничем.",
        ]
    elif state.stage == Stage.VALIDATION:
        lines += [
            f"Задача: {state.task}",
            "Все шаги выполнены. Проверь результат: перечисли, что сделано, "
            "и отметь риски.",
            "Не повторяй план и предыдущие объяснения, дай только отчёт "
            "проверки.",
            "Ответь СТРОГО одним JSON-объектом в блоке ```json ... ``` вида "
            '{"event": "complete_validation", "report": "отчёт проверки"} '
            "и больше ничем.",
        ]
    else:
        lines.append("Задача завершена.")
    return "\n".join(lines)


def _steps(payload: dict) -> tuple[str, ...] | None:
    raw = payload.get("steps", payload.get("plan"))
    if not isinstance(raw, list):
        return None
    steps = tuple(
        item.strip()
        for item in raw
        if isinstance(item, str) and item.strip()
    )
    return steps or None


def _body(payload: dict) -> str | None:
    for key in _BODY_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_object(text: str) -> dict | None:
    for candidate in _json_candidates(text):
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _plan_candidates(text: str):
    fenced = [block.strip() for block in _FENCED.findall(text)]
    for block in reversed(fenced):
        yield block
    if not fenced:
        yield text.strip()


def _json_candidates(text: str):
    for block in reversed([item.strip() for item in _FENCED.findall(text)]):
        if (match := _OBJECT.search(block)):
            yield match.group(0)
        yield block
    if (match := _OBJECT.search(text)):
        yield match.group(0)


def _numbered_steps(text: str) -> tuple[str, ...]:
    return tuple(
        match.group(1)
        for line in text.splitlines()
        if (match := _LIST_ITEM.match(line))
    )
