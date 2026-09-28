import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

import client
import notes_server
import orchestrator
import registry

SERVER_SCRIPT = Path(__file__).with_name("server.py")


# --- notes ---


def test_notes_add_list_search(tmp_path, monkeypatch):
    monkeypatch.setattr(notes_server, "NOTES_PATH", tmp_path / "notes.json")
    notes_server.add_note("MCP", "Протокол для инструментов")
    notes_server.add_note("Wttr", "Погодный сервис")
    listed = notes_server.list_notes()["notes"]
    assert len(listed) == 2
    assert listed[0]["id"] == 1
    found = notes_server.search_notes("протокол")["matches"]
    assert len(found) == 1
    assert found[0]["title"] == "MCP"


# --- registry / client ---


def test_registry_has_four_servers():
    assert sorted(registry.SERVERS) == ["compose", "notes", "scheduler", "weather"]
    assert registry.SERVERS["notes"].script.name == "notes_server.py"


def test_client_calls_notes_server(tmp_path):
    spec = registry.SERVERS["notes"]
    env = {"NOTES_DB": str(tmp_path / "notes.json")}

    async def run():
        await client.call_tool(
            spec, "add_note", {"title": "T", "body": "B"}, python=sys.executable, env=env
        )
        return await client.call_tool(
            spec, "search_notes", {"query": "B"}, python=sys.executable, env=env
        )

    result = asyncio.run(run())
    assert len(result["matches"]) == 1
    assert result["matches"][0]["title"] == "T"


def test_client_make_params_uv_by_default():
    spec = registry.SERVERS["notes"]
    params = client.make_params(spec)
    assert params.command == "uv"
    assert params.args[-1].endswith("notes_server.py")


# --- orchestrator ---


def test_parse_goal_topic_city_reminder():
    params = orchestrator.parse_goal("Узнай погоду в Москве, найди про MCP и напомни проверить")
    assert params["city"] == "Москве"
    assert params["reminder"] is True
    assert "MCP" in params["topic"]


def test_route_full_order():
    steps = orchestrator.route("MCP", city="Москва", reminder=True)
    assert [(s.server, s.tool) for s in steps] == [
        ("weather", "get_weather"),
        ("compose", "search"),
        ("compose", "summarize"),
        ("compose", "save_to_file"),
        ("scheduler", "add_reminder"),
        ("notes", "add_note"),
    ]


def test_route_without_city_skips_weather():
    tools = [s.tool for s in orchestrator.route("MCP")]
    assert "get_weather" not in tools
    assert tools[-1] == "add_note"


def test_route_without_reminder_skips_scheduler():
    servers = [s.server for s in orchestrator.route("MCP", city="Москва")]
    assert "scheduler" not in servers


def test_run_flow_trace_and_data_transfer():
    calls = []

    async def fake(server, tool, args):
        calls.append((server, tool, args))
        if tool == "get_weather":
            return {"city": "Москва", "temperature_c": 10.0}
        if tool == "search":
            return {
                "query": args["query"],
                "results": [{"title": "MCP", "url": "u", "snippet": "Протокол MCP. Ещё MCP."}],
            }
        if tool == "summarize":
            return {"summary": args["text"], "sentence_count": 1}
        if tool == "save_to_file":
            return {"path": "C:/x/out.md", "bytes_written": 10}
        if tool == "add_reminder":
            return {"id": 1, "text": args["text"]}
        if tool == "add_note":
            return {"id": 1, "title": args["title"]}
        raise AssertionError(tool)

    report = asyncio.run(orchestrator.run_flow("Найди про MCP в Москве и напомни", caller=fake))
    assert report["ok"] is True
    assert [t["tool"] for t in report["trace"]] == [
        "get_weather",
        "search",
        "summarize",
        "save_to_file",
        "add_reminder",
        "add_note",
    ]
    by_tool = {t["tool"]: t for t in report["trace"]}
    assert by_tool["summarize"]["args"]["text"] == "MCP. Протокол MCP. Ещё MCP."
    assert by_tool["add_note"]["args"]["body"] == by_tool["summarize"]["result"]["summary"]
    assert report["output_path"] == "C:/x/out.md"


def test_run_flow_records_failure_and_stops():
    async def fake(server, tool, args):
        if tool == "search":
            raise client.ClientError("boom")
        return {"ok": True}

    report = asyncio.run(orchestrator.run_flow("Найди про MCP", caller=fake))
    assert report["ok"] is False
    assert report["trace"][-1]["ok"] is False
    assert "boom" in report["trace"][-1]["error"]
    assert [t["tool"] for t in report["trace"]].count("search") == 1


# --- stdio ---


def orchestrator_params():
    return StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])


async def list_orchestrator_tools():
    async with Client(orchestrator_params()) as mcp_client:
        return (await mcp_client.list_tools()).tools


def test_stdio_lists_four_tools():
    tools = asyncio.run(list_orchestrator_tools())
    assert sorted(t.name for t in tools) == ["call", "list_servers", "plan", "run_flow"]


def test_plan_via_stdio():
    async def run():
        async with Client(orchestrator_params()) as mcp_client:
            result = await mcp_client.call_tool(
                "plan", {"goal": "Узнай погоду в Москве и найди про MCP"}
            )
            assert result.is_error is False
            return result.content[0].text

    text = asyncio.run(run())
    assert "get_weather" in text
    assert "search" in text
    assert "add_note" in text
