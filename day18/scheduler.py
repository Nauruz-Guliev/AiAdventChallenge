"""Ядро планировщика: SQLite-хранилище, расписание, агрегация.

Чистые функции над соединением SQLite — без процессов и сети: этим пользуются
и демон (worker.py), и MCP-сервер (server.py), и тесты.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

DB_FILENAME = "state.db"

KIND_REMINDER = "reminder"
KIND_COLLECT = "collect"
KIND_SUMMARY = "summary"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    city TEXT,
    interval_seconds INTEGER,
    next_run_at INTEGER NOT NULL,
    payload TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    fired_at INTEGER,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    city TEXT NOT NULL,
    temperature_c REAL,
    weather TEXT,
    taken_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    city TEXT NOT NULL,
    period_seconds INTEGER NOT NULL,
    window_start INTEGER NOT NULL,
    window_end INTEGER NOT NULL,
    n INTEGER NOT NULL,
    avg_c REAL,
    min_c REAL,
    max_c REAL,
    created_at INTEGER NOT NULL
);
"""


def db_path() -> Path:
    override = os.environ.get("SCHEDULER_DB")
    if override:
        return Path(override)
    return Path(__file__).with_name(DB_FILENAME)


def now() -> int:
    return int(time.time())


def connect(path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def add_task(conn, kind, *, city=None, interval_seconds=None, next_run_at=None, payload=None):
    created = now()
    when = next_run_at if next_run_at is not None else created
    stored = json.dumps(payload, ensure_ascii=False) if payload is not None else None
    cur = conn.execute(
        "INSERT INTO tasks (kind, city, interval_seconds, next_run_at, payload, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (kind, city, interval_seconds, when, stored, created),
    )
    conn.commit()
    return cur.lastrowid


def add_reminder(conn, text, in_seconds):
    if in_seconds <= 0:
        raise ValueError("in_seconds должен быть больше нуля")
    return add_task(conn, KIND_REMINDER, next_run_at=now() + in_seconds,
                    payload={"text": text})


def add_collection(conn, city, every_seconds):
    if every_seconds <= 0:
        raise ValueError("every_seconds должен быть больше нуля")
    return add_task(conn, KIND_COLLECT, city=city, interval_seconds=every_seconds,
                    next_run_at=now() + every_seconds)


def add_summary(conn, city, every_seconds, window_seconds):
    if every_seconds <= 0 or window_seconds <= 0:
        raise ValueError("every_seconds и window_seconds должны быть больше нуля")
    return add_task(conn, KIND_SUMMARY, city=city, interval_seconds=every_seconds,
                    next_run_at=now() + every_seconds,
                    payload={"window_seconds": window_seconds})


def get_task(conn, task_id):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ValueError(f"Задача {task_id} не найдена")
    return row


def cancel(conn, task_id):
    get_task(conn, task_id)
    conn.execute("UPDATE tasks SET active = 0 WHERE id = ?", (task_id,))
    conn.commit()
    return task_id


def list_tasks(conn):
    return conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()


def list_reminders(conn):
    return conn.execute(
        "SELECT * FROM tasks WHERE kind = ? ORDER BY id", (KIND_REMINDER,)
    ).fetchall()


def due_tasks(conn, at):
    return conn.execute(
        "SELECT * FROM tasks WHERE active = 1 AND next_run_at <= ? ORDER BY next_run_at, id",
        (at,),
    ).fetchall()


def reschedule(conn, task, at):
    conn.execute(
        "UPDATE tasks SET next_run_at = ? WHERE id = ?",
        (at + task["interval_seconds"], task["id"]),
    )
    conn.commit()


def record_sample(conn, task_id, city, temperature_c, weather, taken_at=None):
    conn.execute(
        "INSERT INTO samples (task_id, city, temperature_c, weather, taken_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (task_id, city, temperature_c, weather, taken_at if taken_at is not None else now()),
    )
    conn.commit()


def record_summary(conn, task_id, city, period_seconds, window_start, window_end, agg,
                   created_at=None):
    conn.execute(
        "INSERT INTO summaries (task_id, city, period_seconds, window_start, window_end,"
        " n, avg_c, min_c, max_c, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, city, period_seconds, window_start, window_end, agg["count"],
         agg["avg_c"], agg["min_c"], agg["max_c"],
         created_at if created_at is not None else now()),
    )
    conn.commit()


def mark_reminder_fired(conn, task_id, at=None):
    conn.execute(
        "UPDATE tasks SET active = 0, fired_at = ? WHERE id = ?",
        (at if at is not None else now(), task_id),
    )
    conn.commit()


def aggregate(conn, city, window_seconds, at=None):
    end = at if at is not None else now()
    start = end - window_seconds
    row = conn.execute(
        "SELECT COUNT(*) AS n, AVG(temperature_c) AS avg_c,"
        " MIN(temperature_c) AS min_c, MAX(temperature_c) AS max_c"
        " FROM samples WHERE city = ? AND taken_at >= ? AND taken_at <= ?",
        (city, start, end),
    ).fetchone()
    return {
        "city": city,
        "window_seconds": window_seconds,
        "window_start": start,
        "window_end": end,
        "count": row["n"],
        "avg_c": row["avg_c"],
        "min_c": row["min_c"],
        "max_c": row["max_c"],
    }


def get_summary(conn, city, period_seconds, at=None):
    return aggregate(conn, city, period_seconds, at)


def latest_summary(conn, city=None):
    if city:
        return conn.execute(
            "SELECT * FROM summaries WHERE city = ? ORDER BY id DESC LIMIT 1", (city,)
        ).fetchone()
    return conn.execute("SELECT * FROM summaries ORDER BY id DESC LIMIT 1").fetchone()
