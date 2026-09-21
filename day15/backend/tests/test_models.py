from app.domain.models import (
    LONG_TERM_CATEGORIES,
    Chat,
    LongTermEntry,
    LongTermMemory,
    UsageConfig,
    WorkingMemory,
)


def test_categories_match_spec():
    assert LONG_TERM_CATEGORIES == ("profile", "decisions", "knowledge")


def test_working_memory_empty_and_filled():
    assert WorkingMemory().is_empty is True
    assert WorkingMemory(goal="Собрать ТЗ").is_empty is False
    assert WorkingMemory(constraints=["бюджет 900"]).is_empty is False


def test_long_term_memory_entries_and_count():
    entry = LongTermEntry(
        id="e1", text="аллергия на арахис", source_chat_id="c1", created_at="t"
    )
    long_term = LongTermMemory(knowledge=[entry])

    assert long_term.entries("knowledge") == [entry]
    assert long_term.entries("profile") == []
    assert long_term.total_count() == 1


def test_chat_defaults_to_empty_memory():
    chat = Chat(id="c1", title="T", created_at="a", updated_at="b")

    assert chat.messages == []
    assert chat.working_memory.is_empty is True
    assert chat.working_memory.status == "active"


def test_usage_config_memory_defaults():
    config = UsageConfig()

    assert config.long_term_max_per_category == 50
    assert config.long_term_max_item_chars == 500