import json
import re

from app.domain.task_state import Stage, TaskState

PAUSE_NOTICE = (
    "Задача на паузе. Нажмите «Продолжить», чтобы агент вернулся к работе."
)
PLAN_FORMAT_HINT = (
    "Ответ не содержал корректный план. Верни СТРОГО JSON-массив строк "
    "с шагами в блоке ```json ... ``` и без другого текста."
)

_FENCED = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$")


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


def _numbered_steps(text: str) -> tuple[str, ...]:
    return tuple(
        match.group(1)
        for line in text.splitlines()
        if (match := _LIST_ITEM.match(line))
    )


def _plan_candidates(text: str):
    fenced = [block.strip() for block in _FENCED.findall(text)]
    for block in reversed(fenced):
        yield block
    if not fenced:
        yield text.strip()


def render_plan(steps: tuple[str, ...] | list[str]) -> str:
    items = list(steps)
    lines = "\n".join(
        f"{index}. {step}" for index, step in enumerate(items, 1)
    )
    return f"План работы ({len(items)} шагов):\n{lines}"


def build_task_block(state: TaskState) -> str:
    lines = ["## Состояние задачи", f"Этап: {_stage_label(state.stage)}"]
    if state.stage == Stage.PLANNING:
        lines += [
            f"Задача пользователя: {state.task}",
            "Составь план выполнения задачи из 3–6 шагов.",
            "Ответь СТРОГО JSON-массивом строк в блоке ```json ... ``` "
            "и больше ничем.",
        ]
    elif state.stage == Stage.EXECUTION:
        lines += [
            f"Задача: {state.task}",
            f"Шаг {state.step + 1} из {state.total_steps}: {state.step_label}",
            "Выполни только этот шаг. Не повторяй план и предыдущие объяснения.",
        ]
    elif state.stage == Stage.VALIDATION:
        lines += [
            f"Задача: {state.task}",
            "Все шаги выполнены. Проверь результат: перечисли, что сделано, "
            "и отметь риски.",
            "Не повторяй план и предыдущие объяснения, дай только отчёт проверки.",
        ]
    else:
        lines.append("Задача завершена.")
    return "\n".join(lines)


def _stage_label(stage: Stage) -> str:
    return {
        Stage.PLANNING: "планирование",
        Stage.EXECUTION: "выполнение",
        Stage.VALIDATION: "проверка",
        Stage.DONE: "готово",
    }[stage]
