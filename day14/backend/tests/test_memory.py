from app.application.memory import (
    build_candidate_messages,
    build_long_term_block,
    build_prompt,
    build_working_block,
    parse_candidates,
    parse_command_category,
    parse_memory_command,
)
from app.domain.models import (
    Chat,
    ChatMessage,
    LongTermEntry,
    LongTermMemory,
    WorkingMemory,
)


def entry(text, category="knowledge"):
    return LongTermEntry(
        id=text, text=text, source_chat_id="c1", created_at="t"
    )


def chat_with(messages, working=None):
    return Chat(
        id="c1",
        title="T",
        created_at="a",
        updated_at="b",
        messages=messages,
        working_memory=working or WorkingMemory(),
    )


def test_empty_long_term_and_working_are_not_injected():
    assert build_long_term_block(LongTermMemory()) is None
    assert build_working_block(WorkingMemory()) is None


def test_done_working_memory_is_not_injected():
    working = WorkingMemory(goal="Собрать ТЗ", status="done")

    assert build_working_block(working) is None


def test_long_term_block_lists_categories():
    long_term = LongTermMemory(
        profile=[entry("Науруз", "profile")],
        knowledge=[entry("аллергия на арахис")],
    )

    block = build_long_term_block(long_term)

    assert "## Долговременная память" in block.content
    assert "профиль:" in block.content
    assert "- Науруз" in block.content
    assert "- аллергия на арахис" in block.content


def test_working_block_renders_fields():
    working = WorkingMemory(
        goal="Собрать ТЗ",
        constraints=["бюджет 900"],
        decisions=["PostgreSQL"],
    )

    block = build_working_block(working)

    assert "Цель: Собрать ТЗ" in block.content
    assert "- бюджет 900" in block.content
    assert "- PostgreSQL" in block.content


def test_build_prompt_order_system_longterm_working_history():
    long_term = LongTermMemory(profile=[entry("Науруз", "profile")])
    chat = chat_with(
        [ChatMessage(role="user", content="привет")],
        working=WorkingMemory(goal="ТЗ"),
    )

    prompt = build_prompt(chat, long_term, "SYS")

    assert [m.role for m in prompt] == ["system", "system", "system", "user"]
    assert prompt[0].content == "SYS"
    assert "Долговременная" in prompt[1].content
    assert "Рабочая" in prompt[2].content
    assert prompt[3].content == "привет"


def test_parse_memory_command_variants():
    assert parse_memory_command("запомни: я аллергик") == "я аллергик"
    assert parse_memory_command("Запомни, что люблю Kotlin") == "люблю Kotlin"
    assert parse_memory_command("запомни что тест") == "тест"
    assert parse_memory_command("просто сообщение") is None


def test_parse_candidates_filters_and_caps():
    raw = (
        '[{"text": "аллергия на арахис", "category": "knowledge"},'
        ' {"text": "мусор", "category": "unknown"},'
        ' {"text": "используем PostgreSQL", "category": "decisions"}]'
    )

    result = parse_candidates(raw, 5)

    assert result == [
        {"text": "аллергия на арахис", "category": "knowledge"},
        {"text": "используем PostgreSQL", "category": "decisions"},
    ]


def test_parse_candidates_garbage_returns_empty():
    assert parse_candidates("не json", 5) == []


def test_parse_command_category_falls_back_to_knowledge():
    assert parse_command_category("не json") == "knowledge"
    assert (
        parse_command_category('[{"text": "x", "category": "profile"}]')
        == "profile"
    )


def test_build_candidate_messages_includes_existing():
    long_term = LongTermMemory(knowledge=[entry("аллергия")])

    messages = build_candidate_messages("привет", "ответ", long_term, 3)

    assert messages[0].role == "system"
    assert "аллергия" in messages[1].content
    assert "привет" in messages[1].content