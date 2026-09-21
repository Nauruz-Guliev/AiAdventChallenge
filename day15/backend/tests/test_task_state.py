import pytest

from app.domain.task_state import (
    ALLOWED_TRANSITIONS,
    Event,
    InvalidTransitionError,
    Stage,
    TaskState,
    attempt,
    transition,
)


def _proposed(task="сделай X", steps=("шаг 1", "шаг 2")):
    return TaskState.start(task).propose_plan(list(steps))


def test_new_task_starts_in_planning():
    state = TaskState.start("сделай X")

    assert state.stage == Stage.PLANNING
    assert state.expected_action == "ожидается: агент предложит план"
    assert state.allowed_stages == (Stage.APPROVAL,)
    assert state.to_dict()["active"] is True


def test_transition_table_is_explicit_and_closed():
    assert ALLOWED_TRANSITIONS[Stage.PLANNING] == (Stage.APPROVAL,)
    assert ALLOWED_TRANSITIONS[Stage.APPROVAL] == (Stage.EXECUTION,)
    assert ALLOWED_TRANSITIONS[Stage.EXECUTION] == (
        Stage.EXECUTION,
        Stage.VALIDATION,
    )
    assert ALLOWED_TRANSITIONS[Stage.VALIDATION] == (Stage.DONE,)
    assert ALLOWED_TRANSITIONS[Stage.DONE] == ()


def test_propose_plan_moves_to_approval():
    state = _proposed()

    assert state.stage == Stage.APPROVAL
    assert state.steps == ("шаг 1", "шаг 2")
    assert state.step_number == 0
    assert state.expected_action == "ожидается: пользователь утвердит план"
    assert state.allowed_stages == (Stage.EXECUTION,)


def test_blank_plan_is_rejected():
    with pytest.raises(ValueError):
        TaskState.start("t").propose_plan(["   "])
    with pytest.raises(ValueError):
        TaskState.start("t").propose_plan([])


def test_plan_labels_are_trimmed():
    state = TaskState.start("t").propose_plan(["  a  ", "b"])

    assert state.steps == ("a", "b")


def test_no_execution_before_plan_is_approved():
    state = _proposed()

    with pytest.raises(InvalidTransitionError):
        state.complete_step()


def test_approve_plan_starts_execution():
    state = _proposed().approve_plan()

    assert state.stage == Stage.EXECUTION
    assert state.step_number == 1
    assert state.step_label == "шаг 1"


def test_complete_step_walks_the_plan_then_validation():
    state = _proposed().approve_plan()

    state = state.complete_step()
    assert state.stage == Stage.EXECUTION
    assert state.step_number == 2

    state = state.complete_step()
    assert state.stage == Stage.VALIDATION
    assert state.step_label is None


def test_no_finish_without_validation():
    running = _proposed().approve_plan().complete_step()

    with pytest.raises(InvalidTransitionError):
        transition(running, Event.COMPLETE_VALIDATION)


def test_complete_validation_finishes_task():
    done = _proposed().approve_plan().complete_step().complete_step().complete_validation()

    assert done.stage == Stage.DONE
    assert done.paused is False
    assert done.allowed_stages == ()
    assert done.expected_action == "ожидается: новая задача от пользователя"


def test_dispatcher_accepts_events_and_rejects_unknown():
    proposed = _proposed()
    with pytest.raises(InvalidTransitionError):
        transition(proposed, "finish")


def test_attempt_records_rejection_without_moving_state():
    proposed = _proposed()

    state, rejection = attempt(proposed, Event.COMPLETE_STEP)

    assert state.stage == Stage.APPROVAL
    assert rejection is not None
    assert rejection.event == "complete_step"
    assert rejection.from_stage == "approval"
    assert rejection.to_stage == "execution"
    assert "утвердить план" in rejection.reason
    assert state.rejections == (rejection,)


def test_attempt_returns_none_on_valid_transition():
    state, rejection = attempt(_proposed(), Event.APPROVE_PLAN)

    assert rejection is None
    assert state.stage == Stage.EXECUTION
    assert state.rejections == ()


def test_attempt_records_rejection_for_blank_plan():
    state, rejection = attempt(
        TaskState.start("t"), Event.PROPOSE_PLAN, steps=[]
    )

    assert rejection is not None
    assert state.stage == Stage.PLANNING
    assert state.rejections == (rejection,)
    assert "пуст" in rejection.reason.lower()


def test_rejections_are_bounded():
    state = _proposed()
    for _ in range(8):
        state, _ = attempt(state, Event.COMPLETE_VALIDATION)

    assert len(state.rejections) == 5
    assert state.rejections[-1].event == "complete_validation"


def test_pause_is_noop_on_done():
    done = (
        _proposed()
        .approve_plan()
        .complete_step()
        .complete_step()
        .complete_validation()
    )

    assert done.pause() == done


def test_pause_on_approval_keeps_stage():
    paused = _proposed().pause()

    assert paused.paused is True
    assert paused.stage == Stage.APPROVAL
    assert paused.expected_action == "ожидается: пользователь нажмёт «Продолжить»"


def test_resume_keeps_stage_and_history():
    state, _ = attempt(_proposed(), Event.COMPLETE_STEP)
    paused = state.pause()

    resumed = paused.resume()

    assert resumed.paused is False
    assert resumed.stage == Stage.APPROVAL
    assert resumed.rejections == state.rejections


def test_roundtrip_to_and_from_dict():
    state = _proposed()
    state, _ = attempt(state, Event.COMPLETE_STEP)

    restored = TaskState.from_dict(state.to_dict())

    assert restored == state
    assert restored.to_dict()["stage"] == "approval"
    assert restored.to_dict()["stage_index"] == 1
    assert restored.to_dict()["allowed_stages"] == ["execution"]
    assert restored.to_dict()["rejections"][0]["event"] == "complete_step"
