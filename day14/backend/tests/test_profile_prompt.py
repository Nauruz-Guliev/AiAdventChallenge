import pytest

from app.application.memory import build_memory_trace, build_prompt
from app.application.profiles import (
    build_profile_block,
    build_profile_trace,
    normalize_profile_fields,
)
from app.domain.models import (
    Chat,
    ChatMessage,
    LongTermEntry,
    LongTermMemory,
    UserProfile,
    WorkingMemory,
)


def profile(**overrides):
    data = {
        "id": "p1",
        "title": "Деловой",
        "name": "Айдос",
        "role": "разработчик",
        "tone": "formal",
        "length": "medium",
        "structure": "markdown",
        "constraints": ["без эмодзи", "без воды"],
    }
    data.update(overrides)
    return UserProfile(**data)


def entry(text, category="knowledge"):
    return LongTermEntry(id=text, text=text, source_chat_id="c1", created_at="t")


def chat_with(messages, working=None):
    return Chat(
        id="c1",
        title="T",
        created_at="a",
        updated_at="b",
        messages=messages,
        working_memory=working or WorkingMemory(),
    )


def test_empty_profile_produces_no_block():
    assert build_profile_block(None) is None
    assert build_profile_block(UserProfile(id="p1", title="Нейтральный")) is None


def test_profile_block_renders_all_preferences():
    block = build_profile_block(profile())

    assert block.role == "system"
    assert "## Профиль пользователя" in block.content
    assert "Профиль: Деловой" in block.content
    assert "Имя: Айдос; Роль: разработчик" in block.content
    assert "Отвечай на языке: русский" in block.content
    assert "Тон: деловой" in block.content
    assert "Формат: markdown" in block.content
    assert "- без эмодзи" in block.content


def test_profile_trace_is_none_for_empty_profile():
    assert build_profile_trace(None) is None
    trace = build_profile_trace(profile())
    assert trace["tone"] == "formal"
    assert trace["constraints"] == ["без эмодзи", "без воды"]


def test_build_prompt_puts_profile_before_memory_layers():
    prompt = build_prompt(
        chat_with(
            [ChatMessage(role="user", content="привет")],
            working=WorkingMemory(goal="ТЗ"),
        ),
        LongTermMemory(profile=[entry("Науруз", "profile")]),
        "SYS",
        profile=profile(),
    )

    assert [m.role for m in prompt] == ["system", "system", "system", "system", "user"]
    assert prompt[0].content == "SYS"
    assert "## Профиль пользователя" in prompt[1].content
    assert "Долговременная" in prompt[2].content
    assert "Рабочая" in prompt[3].content
    assert prompt[4].content == "привет"


def test_memory_trace_includes_profile():
    trace = build_memory_trace(chat_with([]), LongTermMemory(), profile=profile())
    assert trace["profile"]["title"] == "Деловой"

    without = build_memory_trace(chat_with([]), LongTermMemory())
    assert without["profile"] is None


def test_normalize_profile_fields_strips_and_validates():
    cleaned = normalize_profile_fields(
        {"name": "  Айдос ", "constraints": [" а ", "", "б"], "tone": "formal"}
    )
    assert cleaned["name"] == "Айдос"
    assert cleaned["constraints"] == ["а", "б"]

    with pytest.raises(ValueError):
        normalize_profile_fields({"tone": "nonsense"})
