"""MCP-сервер 'scheduler': планирование задач и чтение агрегатов."""
from __future__ import annotations

from contextlib import contextmanager

from mcp.server import MCPServer

import scheduler
import sources

mcp = MCPServer("scheduler")


@contextmanager
def db():
    conn = scheduler.connect()
    scheduler.init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


def _row(row) -> dict:
    return {key: row[key] for key in row.keys()}


@mcp.tool()
def add_reminder(text: str, in_seconds: int) -> dict:
    """Поставить напоминание, которое сработает через in_seconds секунд."""
    with db() as conn:
        task_id = scheduler.add_reminder(conn, text, in_seconds)
        return {"id": task_id, "text": text,
                "due_at": scheduler.get_task(conn, task_id)["next_run_at"]}


@mcp.tool()
def list_reminders() -> dict:
    """Список напоминаний: активные и недавно сработавшие."""
    with db() as conn:
        return {"reminders": [_row(row) for row in scheduler.list_reminders(conn)]}


@mcp.tool()
def cancel(task_id: int) -> dict:
    """Выключить задачу по id."""
    with db() as conn:
        scheduler.cancel(conn, task_id)
        return {"id": task_id, "active": False}


@mcp.tool()
def start_collection(city: str, every_seconds: int) -> dict:
    """Периодически собирать погоду в городе каждые every_seconds секунд."""
    with db() as conn:
        task_id = scheduler.add_collection(conn, city, every_seconds)
        return {"id": task_id, "city": city, "every_seconds": every_seconds,
                "next_run_at": scheduler.get_task(conn, task_id)["next_run_at"]}


@mcp.tool()
def start_summary(city: str, every_seconds: int, window_seconds: int) -> dict:
    """Периодически материализовать сводку по городу."""
    with db() as conn:
        task_id = scheduler.add_summary(conn, city, every_seconds, window_seconds)
        return {"id": task_id, "city": city, "every_seconds": every_seconds,
                "window_seconds": window_seconds,
                "next_run_at": scheduler.get_task(conn, task_id)["next_run_at"]}


@mcp.tool()
def collect_now(city: str) -> dict:
    """Сделать внеплановый замер погоды прямо сейчас."""
    try:
        sample = sources.sample_weather(city)
    except sources.SourceError as exc:
        raise ValueError(str(exc)) from exc
    with db() as conn:
        scheduler.record_sample(conn, None, city, sample["temperature_c"],
                                sample["weather"], taken_at=scheduler.now())
    return {"city": city, **sample, "taken_at": scheduler.now()}


@mcp.tool()
def get_summary(city: str, period_seconds: int) -> dict:
    """Агрегат по сырым замерам за последние period_seconds секунд."""
    with db() as conn:
        return scheduler.get_summary(conn, city, period_seconds)


@mcp.tool()
def latest_summary(city: str | None = None) -> dict:
    """Последняя материализованная сводка (по городу или вообще)."""
    with db() as conn:
        row = scheduler.latest_summary(conn, city)
    if row is None:
        raise ValueError("Сводок пока нет")
    return _row(row)


if __name__ == "__main__":
    mcp.run()
