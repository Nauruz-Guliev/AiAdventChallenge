from app.application.memory import build_memory_prompt, merge_memory, parse_memory
from app.domain.models import TaskMemory


def test_parse_memory_extracts_json():
    reply = 'память: {"goal": "цель", "constraints": ["a"], "clarifications": [], "terms": ["t"]}'
    m = parse_memory(reply)
    assert m.goal == "цель"
    assert m.constraints == ["a"]
    assert m.terms == ["t"]


def test_parse_memory_handles_garbage():
    assert parse_memory("нет json").goal == ""


def test_build_memory_prompt_contains_goal():
    prompt = build_memory_prompt(TaskMemory(goal="цель"))
    assert "цель" in prompt


def test_merge_keeps_goal_when_new_empty():
    m = merge_memory(TaskMemory(goal="старая цель"), TaskMemory(goal="", constraints=["x"]))
    assert m.goal == "старая цель"
    assert m.constraints == ["x"]


def test_merge_dedupes_and_unions():
    old = TaskMemory(goal="g", constraints=["a"], clarifications=["b"])
    new = TaskMemory(goal="g", constraints=["a", "c"], terms=["t"])
    m = merge_memory(old, new)
    assert m.goal == "g"
    assert m.constraints == ["a", "c"]
    assert m.clarifications == ["b"]
    assert m.terms == ["t"]
