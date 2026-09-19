import pytest

from app.domain.task_state import InvalidTransitionError, Stage, TaskState


def test_new_task_starts_in_planning():
    state = TaskState.start("сделай X")

    assert state.stage == Stage.PLANNING
    assert state.step == 0
    assert state.total_steps == 0
    assert state.expected_action == "ожидается: агент составляет план"
    assert state.to_dict()["active"] is True


def test_accept_plan_moves_to_execution():
    state = TaskState.start("t").accept_plan(["шаг 1", "шаг 2"])

    assert state.stage == Stage.EXECUTION
    assert state.steps == ("шаг 1", "шаг 2")
    assert state.step_number == 1
    assert state.step_label == "шаг 1"
    assert state.expected_action == "ожидается: агент выполняет шаг 1"


def test_accept_plan_rejected_outside_planning():
    state = TaskState.start("t").accept_plan(["a"])

    with pytest.raises(InvalidTransitionError):
        state.accept_plan(["b"])


def test_blank_plan_is_rejected():
    with pytest.raises(ValueError):
        TaskState.start("t").accept_plan(["   "])
    with pytest.raises(ValueError):
        TaskState.start("t").accept_plan([])


def test_plan_labels_are_trimmed():
    state = TaskState.start("t").accept_plan(["  a  ", "b"])

    assert state.steps == ("a", "b")


def test_advance_step_walks_the_plan_then_validation():
    state = TaskState.start("t").accept_plan(["a", "b"])

    state = state.advance_step()
    assert state.stage == Stage.EXECUTION
    assert state.step_number == 2
    assert state.expected_action == "ожидается: агент выполняет шаг 2"

    state = state.advance_step()
    assert state.stage == Stage.VALIDATION
    assert state.step_number == 2
    assert state.step_label is None
    assert state.expected_action == "ожидается: агент проверяет результат"


def test_advance_step_rejected_outside_execution():
    with pytest.raises(InvalidTransitionError):
        TaskState.start("t").advance_step()


def test_finish_from_validation_clears_pause():
    state = TaskState.start("t").accept_plan(["a"]).advance_step().pause()
    assert state.paused is True

    done = state.finish()

    assert done.stage == Stage.DONE
    assert done.paused is False
    assert done.expected_action == "ожидается: новая задача от пользователя"


def test_finish_rejected_outside_validation():
    with pytest.raises(InvalidTransitionError):
        TaskState.start("t").finish()


def test_pause_is_noop_on_done():
    done = TaskState.start("t").accept_plan(["a"]).advance_step().finish()

    assert done.pause() == done


def test_resume_is_noop_when_not_paused():
    running = TaskState.start("t")

    assert running.resume() == running


def test_paused_expected_action_overrides_stage():
    state = TaskState.start("t").pause()

    assert state.paused is True
    assert state.expected_action == "ожидается: пользователь нажмёт «Продолжить»"


def test_roundtrip_to_and_from_dict():
    state = TaskState.start("t").accept_plan(["a", "b"]).advance_step().pause()

    restored = TaskState.from_dict(state.to_dict())

    assert restored == state
    assert restored.to_dict()["stage"] == "execution"
    assert restored.to_dict()["step"] == 2
    assert restored.to_dict()["stage_index"] == 1
