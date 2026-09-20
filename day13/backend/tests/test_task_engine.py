from app.application.task_engine import build_task_block, parse_plan
from app.domain.task_state import Stage, TaskState


def test_parse_fenced_json_plan():
    text = 'Держи план:\n```json\n["Первый шаг", "Второй шаг"]\n```\nГотово'

    assert parse_plan(text) == ("Первый шаг", "Второй шаг")


def test_parse_uses_last_valid_fence():
    text = '```json\n["старый"]\n```\n```json\n["новый", "ещё"]\n```'

    assert parse_plan(text) == ("новый", "ещё")


def test_parse_bare_json_array():
    assert parse_plan('["раз", "два"]') == ("раз", "два")


def test_parse_numbered_and_bullet_lists_as_fallback():
    assert parse_plan("1. Первый шаг\n2. Второй шаг\n3. Третий шаг") == (
        "Первый шаг",
        "Второй шаг",
        "Третий шаг",
    )
    assert parse_plan("- Собрать данные\n* Написать текст") == (
        "Собрать данные",
        "Написать текст",
    )


def test_parse_returns_none_for_invalid_input():
    assert parse_plan("просто текст без плана") is None
    assert parse_plan("```json\n{not json}\n```") is None
    assert parse_plan('```json\n{"step": "not a list"}\n```') is None
    assert parse_plan("```json\n[]\n```") is None
    assert parse_plan("```json\n[\"  \", 42]\n```") is None


def test_planning_block_requires_json_and_includes_task():
    block = build_task_block(TaskState.start("Сделай отчёт"))

    assert "планирование" in block.lower()
    assert "Сделай отчёт" in block
    assert "json" in block.lower()


def test_execution_block_names_current_step_and_forbids_repeats():
    state = TaskState.start("Сделай отчёт").accept_plan(["Собрать данные", "Написать текст"])

    block = build_task_block(state)

    assert "выполнение" in block.lower()
    assert "шаг 1 из 2" in block.lower()
    assert "Собрать данные" in block
    assert "не повторяй" in block.lower()
    assert "json" not in block.lower()


def test_second_step_block_points_to_second_label():
    state = (
        TaskState.start("t")
        .accept_plan(["Собрать данные", "Написать текст"])
        .advance_step()
    )

    block = build_task_block(state)

    assert "шаг 2 из 2" in block.lower()
    assert "Написать текст" in block


def test_validation_block_asks_for_review_and_forbids_repeats():
    state = (
        TaskState.start("t")
        .accept_plan(["a"])
        .advance_step()
    )
    assert state.stage == Stage.VALIDATION

    block = build_task_block(state)

    assert "проверка" in block.lower()
    assert "не повторяй" in block.lower()
