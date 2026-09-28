import asyncio
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

import pipeline as pipeline_mod
import search_api
import storage
import summarizer
from search_api import SearchError
from storage import StorageError

SERVER_SCRIPT = Path(__file__).with_name("server.py")


def server_params():
    return StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])


async def list_tools():
    async with Client(server_params()) as client:
        return (await client.list_tools()).tools


# --- summarizer ---


def test_summarize_preserves_original_order():
    text = (
        "Первое предложение про погоду. Второе предложение про погоду. "
        "Третье совсем другое. Погода важна."
    )
    result = summarizer.summarize(text, sentences=2)
    assert result["sentence_count"] == 2
    assert result["summary"].startswith("Первое предложение")


def test_summarize_shorter_than_requested_returns_all():
    text = "Одно предложение. Второе предложение."
    result = summarizer.summarize(text, sentences=5)
    assert result["sentence_count"] == 2


def test_summarize_empty_text():
    result = summarizer.summarize("   ")
    assert result["summary"] == ""
    assert result["sentence_count"] == 0


def test_summarize_reduces_length():
    text = "Погода в городе сегодня солнечная. " * 20
    result = summarizer.summarize(text, sentences=2)
    assert result["summary_chars"] < result["original_chars"]


# --- storage ---


def test_save_to_file_writes(tmp_path):
    target = tmp_path / "out" / "note.md"
    result = storage.save_to_file("привет", str(target))
    assert result["path"] == str(target.resolve())
    assert result["bytes_written"] == len("привет".encode("utf-8"))
    assert target.read_text(encoding="utf-8") == "привет"


def test_save_to_file_creates_dir(tmp_path):
    target = tmp_path / "a" / "b" / "c.md"
    storage.save_to_file("x", str(target))
    assert target.exists()


def test_save_to_file_directory_path_raises(tmp_path):
    with pytest.raises(StorageError):
        storage.save_to_file("x", str(tmp_path))


# --- search_api ---


def test_strip_html_removes_tags():
    assert search_api._strip_html('a <span class="x">b</span> c') == "a b c"


def test_search_returns_results(monkeypatch):
    monkeypatch.setattr(
        search_api,
        "_get_json",
        lambda url, params: {
            "query": {
                "search": [
                    {"title": "Model Context Protocol", "snippet": 'Протокол <span class="searchmatch">MCP</span>.'},
                    {"title": "MCP", "snippet": "Другое"},
                ]
            }
        },
    )
    result = search_api.search("MCP")
    assert result["query"] == "MCP"
    assert len(result["results"]) == 2
    assert result["results"][0]["title"] == "Model Context Protocol"
    assert "MCP" in result["results"][0]["snippet"]
    assert "<span" not in result["results"][0]["snippet"]


def test_search_empty_raises(monkeypatch):
    monkeypatch.setattr(search_api, "_get_json", lambda url, params: {"query": {"search": []}})
    with pytest.raises(SearchError):
        search_api.search("Атлантида-ничего")


def test_search_network_error(monkeypatch):
    def boom(url, params):
        raise SearchError("Сеть недоступна")

    monkeypatch.setattr(search_api, "_get_json", boom)
    with pytest.raises(SearchError):
        search_api.search("x")


def test_search_clamps_limit(monkeypatch):
    captured = {}

    def fake(url, params):
        captured["srlimit"] = params["srlimit"]
        return {"query": {"search": [{"title": "t", "snippet": "s"}]}}

    monkeypatch.setattr(search_api, "_get_json", fake)
    search_api.search("x", limit=999)
    assert captured["srlimit"] == "10"


# --- pipeline ---


def test_pipeline_composes_stages(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pipeline_mod.search_api,
        "search",
        lambda query, limit=5: {
            "query": query,
            "results": [
                {"title": "A", "url": "https://x/A", "snippet": "Первое про MCP. Второе про MCP. Третье про MCP."}
            ],
        },
    )
    target = tmp_path / "out.md"
    result = pipeline_mod.run("MCP", path=str(target), sentences=2)
    assert result["stages"]["search"]["result_count"] == 1
    assert result["stages"]["summarize"]["sentence_count"] == 2
    assert result["stages"]["save"]["path"] == str(target.resolve())
    assert result["output_path"] == str(target.resolve())
    assert target.exists()
    assert "MCP" in result["summary"]


def test_pipeline_default_path(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline_mod.storage, "DEFAULT_OUT_DIR", tmp_path)
    monkeypatch.setattr(
        pipeline_mod.search_api,
        "search",
        lambda query, limit=5: {
            "query": query,
            "results": [{"title": "A", "url": "https://x/A", "snippet": "Текст. Ещё текст."}],
        },
    )
    result = pipeline_mod.run("Славный запрос")
    assert result["output_path"].startswith(str(tmp_path))
    assert Path(result["output_path"]).exists()


# --- stdio ---


def test_stdio_lists_four_tools():
    tools = asyncio.run(list_tools())
    assert sorted(t.name for t in tools) == ["pipeline", "save_to_file", "search", "summarize"]


def test_search_schema():
    tools = asyncio.run(list_tools())
    tool = next(t for t in tools if t.name == "search")
    assert tool.input_schema["required"] == ["query"]
    assert tool.input_schema["properties"]["query"]["type"] == "string"


def test_pipeline_schema():
    tools = asyncio.run(list_tools())
    tool = next(t for t in tools if t.name == "pipeline")
    assert tool.input_schema["required"] == ["query"]


def test_summarize_via_stdio():
    async def call():
        async with Client(server_params()) as client:
            result = await client.call_tool("summarize", {"text": "Раз. Два. Три.", "sentences": 2})
            assert result.is_error is False
            return result.content[0].text

    out = asyncio.run(call())
    assert "sentence_count" in out
