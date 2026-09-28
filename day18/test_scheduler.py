import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

import scheduler
import sources
import worker

SERVER_SCRIPT = Path(__file__).with_name("server.py")
TOOL_NAMES = {
    "add_reminder",
    "list_reminders",
    "cancel",
    "start_collection",
    "start_summary",
    "collect_now",
    "get_summary",
    "latest_summary",
}


@pytest.fixture
def conn(tmp_path):
    connection = scheduler.connect(tmp_path / "test.db")
    scheduler.init_db(connection)
    yield connection
    connection.close()


def test_db_path_uses_env(monkeypatch, tmp_path):
    target = tmp_path / "custom.db"
    monkeypatch.setenv("SCHEDULER_DB", str(target))
    assert scheduler.db_path() == target


def test_init_db_creates_tables(conn):
    names = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"tasks", "samples", "summaries"} <= names


def test_add_reminder_due_in_future(conn):
    task_id = scheduler.add_reminder(conn, "чай", 60)
    task = scheduler.get_task(conn, task_id)
    assert task["kind"] == scheduler.KIND_REMINDER
    assert abs(task["next_run_at"] - (scheduler.now() + 60)) <= 2
    assert json.loads(task["payload"])["text"] == "чай"


def test_add_reminder_rejects_non_positive(conn):
    with pytest.raises(ValueError):
        scheduler.add_reminder(conn, "x", 0)


def test_add_collection_rejects_non_positive(conn):
    with pytest.raises(ValueError):
        scheduler.add_collection(conn, "Москва", 0)


def test_due_tasks_only_matured(conn):
    scheduler.add_task(conn, scheduler.KIND_COLLECT, city="М", interval_seconds=5,
                       next_run_at=scheduler.now() - 1)
    scheduler.add_task(conn, scheduler.KIND_COLLECT, city="М", interval_seconds=5,
                       next_run_at=scheduler.now() + 100)
    assert len(scheduler.due_tasks(conn, scheduler.now())) == 1


def test_reschedule_no_catchup(conn):
    task_id = scheduler.add_task(conn, scheduler.KIND_COLLECT, city="М",
                                 interval_seconds=5, next_run_at=1)
    scheduler.reschedule(conn, scheduler.get_task(conn, task_id), 1000)
    assert scheduler.get_task(conn, task_id)["next_run_at"] == 1005


def test_cancel_disables_and_unknown_raises(conn):
    task_id = scheduler.add_collection(conn, "М", 5)
    scheduler.cancel(conn, task_id)
    assert scheduler.get_task(conn, task_id)["active"] == 0
    with pytest.raises(ValueError):
        scheduler.cancel(conn, 999)


def test_aggregate_math(conn):
    scheduler.record_sample(conn, None, "М", 10.0, "ясно", taken_at=1000)
    scheduler.record_sample(conn, None, "М", 20.0, "ясно", taken_at=1001)
    agg = scheduler.aggregate(conn, "М", window_seconds=10, at=1002)
    assert agg["count"] == 2
    assert agg["avg_c"] == 15.0
    assert agg["min_c"] == 10.0
    assert agg["max_c"] == 20.0


def test_aggregate_empty_window(conn):
    agg = scheduler.aggregate(conn, "М", 10, at=1000)
    assert agg["count"] == 0
    assert agg["avg_c"] is None and agg["min_c"] is None and agg["max_c"] is None


def test_latest_summary(conn):
    scheduler.record_summary(conn, None, "М", 60, 0, 60,
                             {"count": 1, "avg_c": 5.0, "min_c": 5.0, "max_c": 5.0})
    assert scheduler.latest_summary(conn, "М")["avg_c"] == 5.0
    assert scheduler.latest_summary(conn, "Другой") is None


def test_sample_weather_maps_weather_api(monkeypatch):
    import weather_api

    monkeypatch.setattr(weather_api, "geocode", lambda city: type("G", (), {
        "name": city, "latitude": 1.0, "longitude": 2.0})())
    monkeypatch.setattr(weather_api, "current_weather",
                        lambda lat, lon: {"temperature_c": 3.5, "weather": "Снег"})
    assert sources.sample_weather("Москва") == {"temperature_c": 3.5, "weather": "Снег"}


def test_sample_weather_wraps_error(monkeypatch):
    import weather_api

    def boom(city):
        raise weather_api.WeatherError("нет сети")

    monkeypatch.setattr(weather_api, "geocode", boom)
    with pytest.raises(sources.SourceError):
        sources.sample_weather("Москва")


def fake_sample(city):
    return {"temperature_c": 7.5, "weather": "Дождь"}


def test_tick_collect_writes_sample_and_reschedules(conn, monkeypatch):
    monkeypatch.setattr(sources, "sample_weather", fake_sample)
    task_id = scheduler.add_task(conn, scheduler.KIND_COLLECT, city="Москва",
                                 interval_seconds=30, next_run_at=scheduler.now() - 1)
    assert worker.tick(conn) == 1
    rows = conn.execute("SELECT * FROM samples").fetchall()
    assert len(rows) == 1 and rows[0]["temperature_c"] == 7.5
    assert scheduler.get_task(conn, task_id)["next_run_at"] >= scheduler.now() + 29


def test_tick_reminder_fires_once(conn):
    task_id = scheduler.add_task(conn, scheduler.KIND_REMINDER, next_run_at=1,
                                 payload={"text": "чай"})
    worker.tick(conn)
    task = scheduler.get_task(conn, task_id)
    assert task["active"] == 0 and task["fired_at"] is not None
    assert worker.tick(conn) == 0


def test_tick_source_error_keeps_schedule(conn, monkeypatch):
    def boom(city):
        raise sources.SourceError("нет сети")

    monkeypatch.setattr(sources, "sample_weather", boom)
    task_id = scheduler.add_task(conn, scheduler.KIND_COLLECT, city="М",
                                 interval_seconds=30, next_run_at=scheduler.now() - 1)
    assert worker.tick(conn) == 1
    assert conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == 0
    assert scheduler.get_task(conn, task_id)["next_run_at"] >= scheduler.now() + 29


def test_tick_summary_materializes(conn):
    moment = scheduler.now()
    scheduler.record_sample(conn, None, "Москва", 10.0, "x", taken_at=moment - 5)
    scheduler.record_sample(conn, None, "Москва", 20.0, "x", taken_at=moment - 3)
    scheduler.add_task(conn, scheduler.KIND_SUMMARY, city="Москва", interval_seconds=60,
                       next_run_at=moment - 1,
                       payload={"window_seconds": 3600})
    worker.tick(conn)
    summary = scheduler.latest_summary(conn, "Москва")
    assert summary["n"] == 2 and summary["avg_c"] == 15.0


def server_params(db):
    env = {**os.environ, "SCHEDULER_DB": str(db)}
    return StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)], env=env)


def test_stdio_lists_all_tools(tmp_path):
    async def go():
        async with Client(server_params(tmp_path / "s.db")) as client:
            return (await client.list_tools()).tools

    assert {tool.name for tool in asyncio.run(go())} == TOOL_NAMES


def test_stdio_add_reminder_and_start_collection(tmp_path):
    async def go():
        async with Client(server_params(tmp_path / "s.db")) as client:
            reminder = await client.call_tool("add_reminder",
                                              {"text": "чай", "in_seconds": 60})
            collection = await client.call_tool(
                "start_collection", {"city": "Москва", "every_seconds": 30})
            return reminder, collection

    reminder, collection = asyncio.run(go())
    assert reminder.is_error is False
    assert collection.is_error is False
