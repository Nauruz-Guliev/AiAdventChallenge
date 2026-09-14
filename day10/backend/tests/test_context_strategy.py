import json

import pytest

from app.application.context_strategy import (
    CONTEXT_MODES,
    assemble_history,
    build_facts_message,
    build_facts_update_messages,
    parse_facts_update,
)
from app.domain.models import Branch, ChatMessage, UsageConfig


def msg(role, content):
    return ChatMessage(role=role, content=content)


@pytest.fixture
def branch():
    messages = [
        msg("user", f"u{i}") if i % 2 == 0 else msg("assistant", f"a{i}")
        for i in range(12)
    ]
    return Branch(id="b", name="main", messages=messages, facts={"цель": "ТЗ"})


@pytest.fixture
def config():
    return UsageConfig(
        context_limit_tokens=8000,
        sliding_window_messages=10,
        facts_max_items=20,
    )


def test_context_modes_exact():
    assert CONTEXT_MODES == ("full", "sliding", "facts", "branching")


def test_full_sends_entire_history(branch, config):
    out = assemble_history("full", branch, msg("user", "new"), config)
    assert out == branch.messages + [msg("user", "new")]


def test_branching_like_full(branch, config):
    out = assemble_history("branching", branch, msg("user", "new"), config)
    assert out == branch.messages + [msg("user", "new")]


def test_sliding_keeps_window_plus_new(branch, config):
    out = assemble_history("sliding", branch, msg("user", "new"), config)
    assert out == branch.messages[-10:] + [msg("user", "new")]


def test_facts_block_plus_window(branch, config):
    out = assemble_history("facts", branch, msg("user", "new"), config)
    assert out[0].role == "system" and "цель: ТЗ" in out[0].content
    assert out[1:] == branch.messages[-10:] + [msg("user", "new")]


def test_facts_mode_without_facts_is_plain_window(config):
    branch = Branch(id="b", name="main", messages=[msg("user", "u1")])
    out = assemble_history("facts", branch, msg("user", "new"), config)
    assert out == [msg("user", "u1"), msg("user", "new")]


def test_unknown_mode_rejected(branch, config):
    with pytest.raises(ValueError):
        assemble_history("summary", branch, msg("user", "new"), config)


def test_build_facts_message_empty_none():
    assert build_facts_message({}) is None


def test_facts_update_prompt_includes_current_and_new():
    messages = build_facts_update_messages({"цель": "ТЗ"}, "бюджет 1200", 20)
    assert messages[0].role == "system" and "facts" in messages[0].content.lower()
    assert "цель" in messages[0].content + messages[1].content
    assert "бюджет 1200" in messages[1].content


def test_parse_facts_update_plain_json_and_cap():
    raw = json.dumps({f"k{i}": str(i) for i in range(30)}, ensure_ascii=False)
    parsed = parse_facts_update(raw, limit=20)
    assert len(parsed) == 20 and parsed["k0"] == "0"


def test_parse_facts_update_fenced_and_prose():
    result = parse_facts_update(
        'Вот обновлённый JSON:\n```json\n{"a": 1}\n```', 20
    )
    assert result == {"a": "1"}


def test_parse_facts_update_garbage_returns_none():
    assert parse_facts_update("фактов не нашлось", 20) is None
