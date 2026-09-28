# Day 18 — Планировщик и фоновые задачи (конспект)

День 17 дал инструмент, который отвечает **на запрос**. День 18 — инструмент,
который работает **во времени**: помнит задачи, тикает и копит данные, пока агент
закрыт, и отдаёт агрегированный результат при обращении.

## Главное ограничение: MCP — pull-модель

MCP-сервер **не может сам** «толкнуть» сообщение агенту. Значит «периодически
выдаёт сводку» реализуется так:

```
демон (по расписанию) ──► материализует сводки в SQLite
агент  (когда спросит)  ──► читает их инструментом latest_summary/get_summary
```

Автозапуск «агент сам раз в час» — отдельное упражнение через планировщик ОС.

## Архитектура: два процесса + одна SQLite

```
opencode ──stdio──► server.py ─┐
                                ├─► day18/state.db
worker.py (демон, тик 1 c) ─────┘
   └──► sources.sample_weather() ──► day17/weather_api.py ──► wttr.in
```

- `server.py` — MCP-сервер: принимает задачи и отдаёт агрегаты.
- `worker.py` — демон: выполняет задачи по расписанию, живёт независимо.
- Общее состояние — в SQLite. Никакой общей памяти: каждый процесс открывает БД
  сам. Поэтому всё можно перезапускать в любом порядке.

## Ядро `scheduler.py`

Вся логика и SQL — в чистых функциях над соединением: их вызывают и демон, и
сервер, и тесты. Три таблицы:

```sql
tasks(id, kind, city, interval_seconds, next_run_at, payload,
      active, fired_at, acknowledged, created_at)
samples(id, task_id, city, temperature_c, weather, taken_at)
summaries(id, task_id, city, period_seconds, window_start, window_end,
          n, avg_c, min_c, max_c, created_at)
```

`kind ∈ {reminder, collect, summary}`. У `reminder` интервала нет — срабатывает
один раз. Время — epoch-секунды (int, UTC) через `scheduler.now()`.

**Выбор созревших задач:**

```python
def due_tasks(conn, at):
    return conn.execute(
        "SELECT * FROM tasks WHERE active = 1 AND next_run_at <= ? ORDER BY next_run_at, id",
        (at,)).fetchall()
```

**Перенос без «догона»** — важный момент:

```python
def reschedule(conn, task, at):
    conn.execute("UPDATE tasks SET next_run_at = ? WHERE id = ?",
                 (at + task["interval_seconds"], task["id"]))
```

Если демон был выключен час, задача выполнится **один раз**, а не залпом за весь
простой. Новый срок считается от момента выполнения (`at + interval`), поэтому
расписание не «разъезжается».

## Демон `worker.py`

Раз в секунду: выбрать созревшие задачи и выполнить каждую по типу.

- `collect` → `sources.sample_weather(city)` → `samples` → перенос;
- `summary` → `aggregate()` за окно → `summaries` → перенос;
- `reminder` → `fired_at=now`, `active=0`.

Ошибка одной задачи логируется и **не роняет** демон; при недоступном источнике
замер пропускается, но срок всё равно переносится (расписание не теряется).

```python
if kind == scheduler.KIND_COLLECT:
    try:
        sample = sources.sample_weather(task["city"])
    except sources.SourceError as exc:
        print(f"[worker] {task['city']}: источник недоступен: {exc}", file=sys.stderr)
    else:
        scheduler.record_sample(conn, task["id"], task["city"],
                                sample["temperature_c"], sample["weather"], taken_at=at)
    scheduler.reschedule(conn, task, at)
```

## Источник `sources.py`

Тонкая обёртка над днём 17: берём город, получаем `temperature_c` и `weather`.
Ошибки `WeatherError` → `SourceError`. Так домен сбора отделён от планировщика —
демон не знает, откуда данные.

## MCP-сервер: 8 инструментов

| Инструмент | Что делает |
|---|---|
| `add_reminder(text, in_seconds)` | разовое напоминание |
| `list_reminders()` | активные + сработавшие |
| `cancel(task_id)` | выключить задачу |
| `start_collection(city, every_seconds)` | периодический сбор |
| `start_summary(city, every_seconds, window_seconds)` | периодическая сводка |
| `collect_now(city)` | внеплановый замер |
| `get_summary(city, period_seconds)` | агрегат за окно |
| `latest_summary(city=None)` | последняя материализованная сводка |

Сервер не выполняет задачи — только пишет их в БД и читает агрегаты. Выполняет
демон. Разделение ответственности: сервер = интерфейс, демон = исполнитель.

## Демонстрация 24/7

1. Терминал A: `python worker.py` — тикает.
2. opencode: `start_collection("Москва", 30)`, `start_summary("Москва", 60, 3600)`,
   `add_reminder("перерыв", 20)`.
3. Закрыть opencode → демон продолжает писать `samples`.
4. Открыть → `latest_summary` → агент выдаёт сводку. Это и есть «24/7».

## Агрегация

`aggregate(conn, city, window_seconds, at)` считает по сырым замерам:

```sql
SELECT COUNT(*) AS n, AVG(temperature_c) AS avg_c,
       MIN(temperature_c) AS min_c, MAX(temperature_c) AS max_c
FROM samples WHERE city = ? AND taken_at >= ? AND taken_at <= ?
```

Пустое окно → `count=0`, значения `None` (не падаем).

## Тесты

19 офлайн-тестов: ядро (сроки/перенос/отмена/агрегация), воркер с фейковым
источником, stdio-интеграция (8 инструментов + вызовы). Сеть не нужна.

```powershell
& ".venv\Scripts\python.exe" -m pytest -q   # 19 passed
```

## Упражнения

1. Добавь `pause`/`resume` задачи (поле `active` уже есть).
2. Второй источник (например, курс валют) — расширь `sources.py`.
3. Автозапуск демона через Windows Task Scheduler.
4. «Доставка» сводки: пусть демон пишет ещё и в файл `outbox.jsonl`.

## Частые вопросы

- **Почему не APScheduler?** Свой цикл на stdlib прозрачнее и без зависимостей;
  схема та же (tasks + next_run_at).
- **Почему два процесса, а не один?** MCP-сервер живёт, пока открыт opencode.
  Демон должен работать независимо — отсюда отдельный процесс и общая БД.
- **Что если оба пишут в SQLite?** Демон — фактически один писатель, сервер почти
  всегда читает; включён WAL, транзакции короткие.
