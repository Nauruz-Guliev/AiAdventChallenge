import asyncio

from client import call_add, fetch_tools, format_tools


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
