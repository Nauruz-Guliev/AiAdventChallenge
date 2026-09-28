"""Демон: тикает и выполняет созревшие задачи из SQLite."""
from __future__ import annotations

import asyncio
import json
import sys

import scheduler
import sources

TICK_SECONDS = 1


def _payload(task) -> dict:
    return json.loads(task["payload"]) if task["payload"] else {}


def execute_task(conn, task) -> None:
    at = scheduler.now()
    kind = task["kind"]
    if kind == scheduler.KIND_REMINDER:
        print(f"[worker] напоминание #{task['id']}: {_payload(task).get('text', '')}")
        scheduler.mark_reminder_fired(conn, task["id"], at)
        return
    if kind == scheduler.KIND_COLLECT:
        try:
            sample = sources.sample_weather(task["city"])
        except sources.SourceError as exc:
            print(f"[worker] {task['city']}: источник недоступен: {exc}", file=sys.stderr)
        else:
            scheduler.record_sample(conn, task["id"], task["city"],
                                    sample["temperature_c"], sample["weather"], taken_at=at)
        scheduler.reschedule(conn, task, at)
        return
    if kind == scheduler.KIND_SUMMARY:
        window = int(_payload(task).get("window_seconds", 0))
        agg = scheduler.aggregate(conn, task["city"], window, at=at)
        scheduler.record_summary(conn, task["id"], task["city"], window,
                                 agg["window_start"], agg["window_end"], agg, created_at=at)
        scheduler.reschedule(conn, task, at)
        return
    print(f"[worker] неизвестный тип задачи: {kind}", file=sys.stderr)


def tick(conn) -> int:
    due = scheduler.due_tasks(conn, scheduler.now())
    for task in due:
        try:
            execute_task(conn, task)
        except Exception as exc:  # одна задача не должна ронять демон
            print(f"[worker] ошибка задачи #{task['id']}: {exc}", file=sys.stderr)
    return len(due)


async def run(tick_seconds: int = TICK_SECONDS) -> None:
    conn = scheduler.connect()
    scheduler.init_db(conn)
    print(f"[worker] запущен, БД: {scheduler.db_path()}, тик {tick_seconds} c")
    try:
        while True:
            tick(conn)
            await asyncio.sleep(tick_seconds)
    finally:
        conn.close()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n[worker] остановлен")


if __name__ == "__main__":
    main()
