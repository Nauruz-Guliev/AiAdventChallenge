# Day 18 — Планировщик и фоновые задачи (MCP + демон + SQLite)

## Цель

Сделать MCP-инструмент с **отложенным и периодическим** выполнением: агент ставит
напоминания и задачи периодического сбора, отдельный **демон** выполняет их по
расписанию **24/7**, данные и расписание хранятся в **SQLite**, а инструмент
возвращает **агрегированный результат** (сводку). Демонстрация: сборщик собирает
погоду (переиспользуя day17), работает независимо от открытого opencode, а агент
по запросу выдаёт сводку за период.

## Вне-цели (YAGNI)

- Без APScheduler и вообще новых зависимостей: только stdlib (`sqlite3`, `asyncio`)
  и `mcp`/`pytest`. Погода — через `day17/weather_api.py`.
- Только stdio-транспорт; без HTTP/SSE.
- Без UI.
- Без блокировок/нескольких воркеров (один демон = один писатель).
- Не трогаем глобальный конфиг `~/.config/opencode/opencode.json`; подключение
  **проектное** (`opencode.json` в корне репозитория).
- Не пишем собственный LLM/агент — агентом выступает opencode.

## Ключевое ограничение (важно понять)

MCP — **pull-модель**: сервер не может «толкнуть» сообщение агенту. Поэтому
«периодически выдаёт сводку» реализуется так: демон по расписанию **материализует**
сводки в БД, а агент читает их через инструмент (`latest_summary`/`get_summary`)
при обращении. Автозапуск «агент сам раз в час» — отдельное упражнение через
планировщик ОС (Task Scheduler), вне рамок этого дня.

## Архитектура

Два процесса, одна общая БД `day18/state.db` (SQLite, режим WAL):

```
opencode (агент)
   │  stdio / JSON-RPC
   ▼
day18/server.py   (MCP: планирование задач + чтение агрегатов) ─┐
                                                                 ├─► day18/state.db
day18/worker.py   (демон: тикает раз в секунду, выполняет)  ─────┘
   │
   ▼  sources.sample_weather(city)
day17/weather_api.py  →  wttr.in
```

Выбранный вариант координации — **БД как единственный источник правды**:
никакой общей памяти между процессами, всё состояние в SQLite, планировщик
stateless. Это подмножество job-queue с блокировками; блокировки можно добавить
позже без ломки схемы.

### Дерево `day18/`

```
day18/
  scheduler.py            # ядро: схема/CRUD/выбор due-задач/агрегация (чистые функции)
  sources.py              # источник данных: sample_weather(city) через day17
  worker.py               # демон: asyncio-тик, выполняет задачи
  server.py               # MCP-сервер "scheduler": 8 инструментов
  test_scheduler.py       # pytest: ядро + воркер (фейк-источник) + stdio
  requirements.txt        # mcp>=2,<3 ; pytest>=8
  pyproject.toml          # pythonpath=., testpaths=.
  .gitignore              # .venv/, __pycache__/, .pytest_cache/, state.db*, video-script.html
  opencode.example.jsonc  # образец проектного конфига для копирования в корень
  README.md
  LESSON.md
  lesson.html
  video-script.html
docs/superpowers/specs/2026-09-28-day18-scheduler-design.md   # этот документ
opencode.json             # (в корне, создаёт пользователь) регистрация scheduler
```

### `scheduler.py` — ядро (без процессов)

Всё общение с БД и логика расписания — здесь, чтобы это тестировать напрямую.

- `db_path()` — `Path(__file__).with_name("state.db")`, переопределяется `SCHEDULER_DB`.
- `connect(path)` — открывает SQLite, включает `PRAGMA journal_mode=WAL`,
  `PRAGMA foreign_keys=ON`; `init_db(conn)` создаёт таблицы.
- `now()` — epoch-секунды (int, UTC).
- CRUD задач: `add_reminder(conn, text, in_seconds)`, `add_collection(conn, city,
  every_seconds)`, `add_summary(conn, city, every_seconds, window_seconds)`,
  `cancel(conn, task_id)`, `list_tasks(conn)`, `list_reminders(conn)`.
- `due_tasks(conn, at)` → выборка `active=1 AND next_run_at <= at`.
- `reschedule(conn, task, at)` → `next_run_at = at + interval` (просрочку не
  «догоняем» пачкой: один запуск, без залпа после простоя).
- Запись результатов: `record_sample(...)`, `record_summary(...)`,
  `mark_reminder_fired(conn, task_id, at)`.
- Агрегация: `aggregate(conn, city, window_seconds, at)` →
  `{count, avg_c, min_c, max_c, window_start, window_end}` над `samples`
  (пустое окно → `count=0`, значения `None`).
- `get_summary(conn, city, period_seconds)`, `latest_summary(conn, city=None)`.

### `sources.py` — источник данных

- `sample_weather(city) -> {"temperature_c": float, "weather": str}` — переиспользует
  `day17/weather_api.py` (добавляем `../day17` в `sys.path` при импорте).
- Ошибки источника → `SourceError`; воркер её логирует, **не** роняет процесс и не
  пишет замер (пропуск), но всё равно переносит `next_run_at`, чтобы расписание не
  терялось.
- Тесты подменяют `sources.sample_weather` фейком — сеть не нужна.

### `worker.py` — демон

- `asyncio`-цикл, `TICK_SECONDS = 1`.
- Каждый тик: `due = scheduler.due_tasks(conn, now())`; для каждой задачи:
  - `collect` → `sources.sample_weather(city)` → `record_sample` → `reschedule`;
  - `summary` → `aggregate(...)` → `record_summary` → `reschedule`;
  - `reminder` → `mark_reminder_fired(...)` (одноразово, `active=0`).
- Ошибки одной задачи не останавливают другие (try/except на задачу, лог в stderr).
- Аккуратное завершение по `Ctrl+C` (KeyboardInterrupt / отмена задачи).
- Запуск: `python worker.py`; БД — та же, что у сервера (общий `SCHEDULER_DB`/путь).

### `server.py` — MCP-сервер

`MCPServer("scheduler")`. Инструменты (возврат — `dict`; ошибки → `ValueError`,
чтобы SDK отдал `isError`):

| Инструмент | Параметры | Возврат / эффект |
|---|---|---|
| `add_reminder` | `text: str`, `in_seconds: int` | `{id, text, due_at}` — разовая задача |
| `list_reminders` | — | активные + недавно сработавшие (`fired_at`) |
| `cancel` | `task_id: int` | `{id, active: false}` |
| `start_collection` | `city: str`, `every_seconds: int` | `{id, city, every_seconds, next_run_at}` |
| `start_summary` | `city: str`, `every_seconds: int`, `window_seconds: int` | `{id, city, ...}` |
| `collect_now` | `city: str` | внеплановый замер; `{city, temperature_c, weather, taken_at}` |
| `get_summary` | `city: str`, `period_seconds: int` | агрегат по сырым замерам за окно |
| `latest_summary` | `city: str \| None = None` | последняя материализованная сводка |

Имя сервера в opencode префиксует инструменты: `scheduler_add_reminder` и т.д.
`every_seconds`/`in_seconds` — секунды (для наглядного демо); проверяем `> 0`.

## Модель данных

```sql
tasks(id INTEGER PK, kind TEXT, city TEXT, interval_seconds INTEGER,
      next_run_at INTEGER, payload TEXT, active INTEGER DEFAULT 1,
      fired_at INTEGER, acknowledged INTEGER DEFAULT 0, created_at INTEGER)
-- kind ∈ {'reminder','collect','summary'}; reminder: interval_seconds IS NULL
samples(id INTEGER PK, task_id INTEGER, city TEXT, temperature_c REAL,
        weather TEXT, taken_at INTEGER)
summaries(id INTEGER PK, task_id INTEGER, city TEXT, period_seconds INTEGER,
          window_start INTEGER, window_end INTEGER, n INTEGER,
          avg_c REAL, min_c REAL, max_c REAL, created_at INTEGER)
```

Время — epoch-секунды (int, UTC); для показа конвертируем в локальное.

## Конфигурация и БД

- `SCHEDULER_DB` (env) задаёт путь к БД; по умолчанию
  `day18/state.db` — **относительно файла `scheduler.py`**, а не cwd, чтобы демон и
  сервер (запущенные из разных мест) смотрели в одну БД.
- В `.gitignore`: `state.db`, `state.db-wal`, `state.db-shm`, `.venv/`,
  `__pycache__/`, `.pytest_cache/`, `video-script.html`.
- Тесты используют `tmp_path`/`SCHEDULER_DB` → реальная БД не задевается.

## Регистрация в opencode

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "scheduler": {
      "type": "local",
      "command": ["uv", "run", "--no-project", "--with", "mcp>=2,<3", "server.py"],
      "cwd": "day18",
      "enabled": true,
      "timeout": 60000
    }
  }
}
```

`SCHEDULER_DB` можно не указывать — по умолчанию БД лежит рядом с `scheduler.py`
(`day18/state.db`) независимо от cwd. Переменная нужна лишь чтобы увести БД в
другое место (её же используют тесты).

Демон запускается **отдельно** в своём терминале — его opencode не поднимает:
`python worker.py` (или `& ".venv\Scripts\python.exe" worker.py`).

## Тесты (офлайн, без сети) — ориентир ≥15

`test_scheduler.py`:

- ядро: `add_reminder`/`add_collection` создают задачи; `due_tasks` до/после срока;
  `reschedule` = `now + interval` (без догона); `cancel` выключает; `aggregate`
  (avg/min/max, пустое окно → `count=0`, `None`); `latest_summary`.
- воркер: с фейковым `sources.sample_weather` тик выполняет `collect` → появился
  `sample` и сдвинулся `next_run_at`; `reminder` срабатывает один раз; ошибка
  источника не роняет тик.
- stdio-интеграция: `tools/list` содержит 8 инструментов; вызовы
  `add_reminder`, `start_collection`, `collect_now` (с фейком), `get_summary`
  работают против временной БД.

Запуск: `& ".venv\Scripts\python.exe" -m pytest -q`.

## Демонстрация (видео)

1. Терминал A: `python worker.py` (демон тикает).
2. opencode: агент вызывает `scheduler_start_collection("Москва", 30)` и
   `scheduler_start_summary(...)`, затем `scheduler_add_reminder("перерыв", 20)`.
3. **Закрыть opencode** → демон продолжает собирать (видно по росту `samples`).
4. Снова открыть opencode → `get_summary`/`latest_summary` → агент выдаёт сводку.
   Это доказывает «24/7».
5. `pytest -q` → все зелёные.

## Критерии готовности

- [ ] `scheduler.py`, `sources.py`, `worker.py`, `server.py` реализованы.
- [ ] `pytest -q` зелёный (офлайн).
- [ ] Живой сбор работает (Москва, wttr.in), сводка считается.
- [ ] Демон переживает закрытие opencode и продолжает писать замеры.
- [ ] `day18/opencode.example.jsonc` регистрирует `scheduler` (в корень копирует
      пользователь).
- [ ] В opencode агент вызывает инструменты и отдаёт сводку.
- [ ] Обновлены `README.md`, `LESSON.md`, `lesson.html`, `video-script.html`.
- [ ] Коммит и push в `origin/main`.

## Риски и заметки

- MCP не push — «периодичность» обеспечивает демон, агент читает по запросу.
- wttr.in может отдавать rate-limit при частом сборе → `SourceError`, тик
  продолжается; интервал для демо держим разумным (≥30 c).
- SQLite конкурентность: WAL + короткие транзакции; один писатель (демон) —
  сервер почти всегда читает, конфликтов нет.
- Демон и сервер обязаны открывать **одну и ту же** БД (общий `SCHEDULER_DB`).
- Кириллица: JSON-RPC в UTF-8; вывод БД/логов — UTF-8.
