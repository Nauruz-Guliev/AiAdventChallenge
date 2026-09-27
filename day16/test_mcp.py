import asyncio
import json

import pytest

from client import (
    bind_positional,
    call_add,
    fetch_tools,
    format_result,
    format_tools,
    parse_input,
)


def test_connection_returns_three_tools():
    tools = asyncio.run(fetch_tools())
    assert sorted(tool.name for tool in tools) == ["add", "echo", "today"]


def test_add_has_expected_input_schema():
    tools = asyncio.run(fetch_tools())
    add = next(tool for tool in tools if tool.name == "add")
    assert add.description
    assert set(add.input_schema["properties"]) == {"a", "b"}
    assert add.input_schema["required"] == ["a", "b"]


def test_mcp_round_trip_calls_add():
    result = asyncio.run(call_add(2, 3))
    assert result.structured_content == {"result": 5}


def test_format_tools_is_readable():
    tools = asyncio.run(fetch_tools())
    text = format_tools(tools, color=False, show_schema=True)
    assert "Инструментов: 3" in text
    assert "Add two numbers." in text
    assert "a: integer" in text
    assert "b: integer" in text
    assert "text: string" in text
    assert "Аргументы: нет" in text
    assert "Схема:" in text


def test_parse_input_splits_tool_and_args():
    assert parse_input("add 2 3") == ("add", ["2", "3"])
    assert parse_input('echo "два слова"') == ("echo", ["два слова"])
    assert parse_input("   ") == ("", [])


def test_bind_positional_coerces_types():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    }
    assert bind_positional(schema, ["2", "3"]) == {"a": 2, "b": 3}


def test_bind_positional_keeps_strings():
    schema = {"properties": {"text": {"type": "string"}}, "required": ["text"]}
    assert bind_positional(schema, ["привет"]) == {"text": "привет"}


def test_bind_positional_rejects_wrong_count():
    schema = {
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    }
    with pytest.raises(ValueError):
        bind_positional(schema, ["2"])


def test_bind_positional_rejects_bad_type():
    schema = {
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    }
    with pytest.raises(ValueError):
        bind_positional(schema, ["2", "x"])


def test_format_result_is_mcp_json():
    result = asyncio.run(call_add(2, 3))
    data = json.loads(format_result(result))
    assert data["structuredContent"] == {"result": 5}
    assert data["content"][0]["text"] == "5"
