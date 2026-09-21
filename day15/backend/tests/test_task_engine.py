from app.application.task_engine import (
    build_rejection_notice,
    build_task_block,
    parse_plan,
    parse_proposal,
)
from app.domain.task_state import Event, Stage, TaskState, attempt


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


def test_proposal_reads_plan_envelope():
    text = '```json\n{"event": "propose_plan", "steps": ["a", "b"]}\n```'

    proposal = parse_proposal(text, Event.PROPOSE_PLAN)

    assert proposal.event == "propose_plan"
    assert proposal.steps == ("a", "b")


def test_proposal_reads_result_and_report_bodies():
    step = parse_proposal(
        '```json\n{"event": "complete_step", "result": "шаг сделан"}\n```',
        Event.COMPLETE_STEP,
    )
    report = parse_proposal(
        '{"event": "complete_validation", "report": "всё проверено"}',
        Event.COMPLETE_VALIDATION,
    )

    assert step.text == "шаг сделан"
    assert report.text == "всё проверено"


def test_proposal_keeps_unknown_event_for_rejection():
    proposal = parse_proposal('{"event": "finish"}', Event.COMPLETE_STEP)

    assert proposal.event == "finish"


def test_proposal_falls_back_to_expected_event():
    plain = parse_proposal("просто текст", Event.COMPLETE_STEP)
    fallback = parse_proposal('```json\n["a", "b"]\n```', Event.PROPOSE_PLAN)

    assert plain.event == "complete_step"
    assert plain.text == "просто текст"
    assert fallback.event == "propose_plan"
    assert fallback.steps == ("a", "b")


def test_planning_block_requires_transition_envelope():
    block = build_task_block(TaskState.start("Сделай отчёт"))

    assert "планирование" in block.lower()
    assert "Сделай отчёт" in block
    assert "propose_plan" in block
    assert "не начинай выполнение" in block.lower()


def test_approval_block_lists_plan_and_waits():
    state = TaskState.start("Сделай отчёт").propose_plan(["Собрать данные"])

    block = build_task_block(state)

    assert "утверждение плана" in block.lower()
    assert "1. Собрать данные" in block
    assert "после утверждения" in block.lower()


def test_execution_block_names_current_step_and_requires_envelope():
    state = TaskState.start("Сделай отчёт").propose_plan(
        ["Собрать данные", "Написать текст"]
    ).approve_plan()

    block = build_task_block(state)

    assert "выполнение" in block.lower()
    assert "шаг 1 из 2" in block.lower()
    assert "Собрать данные" in block
    assert "не повторяй" in block.lower()
    assert "complete_step" in block


def test_second_step_block_points_to_second_label():
    state = (
        TaskState.start("t")
        .propose_plan(["Собрать данные", "Написать текст"])
        .approve_plan()
        .complete_step()
    )

    block = build_task_block(state)

    assert "шаг 2 из 2" in block.lower()
    assert "Написать текст" in block


def test_validation_block_asks_for_review_and_requires_envelope():
    state = (
        TaskState.start("t")
        .propose_plan(["a"])
        .approve_plan()
        .complete_step()
    )
    assert state.stage == Stage.VALIDATION

    block = build_task_block(state)

    assert "проверка" in block.lower()
    assert "не повторяй" in block.lower()
    assert "complete_validation" in block


def test_rejection_notice_names_stage_and_reason():
    state, rejection = attempt(
        TaskState.start("t").propose_plan(["a"]), Event.COMPLETE_STEP
    )

    notice = build_rejection_notice(rejection, state)

    assert "⚠" in notice
    assert "утверждение плана" in notice
    assert "сначала нужно утвердить план" in notice
