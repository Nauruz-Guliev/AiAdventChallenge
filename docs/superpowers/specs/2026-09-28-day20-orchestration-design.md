# Day 20 — Оркестрация MCP (несколько серверов, длинный флоу)

## Цель

Зарегистрировать несколько MCP-серверов и построить **сервер-оркестратор**, который:

1. **выбирает нужный инструмент** под цель (маршрутизация);
2. **корректно маршрутизирует** вызовы по серверам;
3. **выполняет длинный флоу** взаимодействия и возвращает `trace` — доказательство
   выбора и порядка вызовов.

Демонстрация: один вызов `orchestrator_run_flow("…")` проходит по инструментам
**четырёх** серверов (weather, compose, scheduler, notes) в правильном порядке, а
`orchestrator_plan(goal)` показывает выбранную последовательность **до** выполнения.

## Вне-цели (YAGNI)

- Никакого NLU/LLM внутри оркестратора: маршрутизация — **rule-based** по ключевым
  словам (учебный роутер, а не продакшн-парсер). Явно задокументировано.
- Не поднимаем все серверы постоянно: `run_flow` открывает stdio-клиент на сервер
  по мере надобности (через `AsyncExitStack`, по одному клиенту на сервер).
- Не трогаем глобальный конфиг; регистрация — проектная + оверрайд (как д18/19).
- Без HTTP/SSE, без UI, без БД (кроме JSON-файла заметок).
- Не пишем агента — агентом остаётся opencode.

## Ключевая идея

День 19 — композиция **внутри** одного сервера. День 20 — оркестрация **между**
серверами: оркестратор сам является **MCP-клиентом** для других серверов.

```
opencode (агент)
   │ stdio
   ▼
day20/server.py  (MCP "orchestrator": list_servers, plan, run_flow, call)
   │  MCP-клиенты по stdio
   ├─► day17/server.py   (weather)     ┐
   ├─► day19/server.py   (compose)     │  длинный флоу:
   ├─► day18/server.py   (scheduler)   │  weather → search → summarize →
   └─► day20/notes_server.py (notes)   ┘  save → reminder → note
```

### Пул серверов

| Сервер | Откуда | Инструмент во флоу |
|---|---|---|
| `weather` | day17 | `get_weather(city)` |
| `compose` | day19 | `search`, `summarize`, `save_to_file` |
| `scheduler` | day18 | `add_reminder(text, in_seconds)` |
| `notes` | **новый** | `add_note(title, body)` |

### Длинный флоу (Research & schedule)

```
1 weather.get_weather(city)          (если указан город)
2 compose.search(topic)
3 compose.summarize(text=$search_text)
4 compose.save_to_file(content=$markdown)
5 scheduler.add_reminder(text, in_seconds)   (если просили напомнить)
6 notes.add_note(title=topic, body=$summary)
```

Данные передаются по цепочке: `search.results` → `$search_text` → `summarize` →
`$summary`/`$markdown` → `save`/`add_note`. Шаги 1 и 5 включаются **условно** —
это и есть выбор инструментов под запрос.

## Архитектура

### Дерево `day20/`

```
day20/
  notes_server.py         # MCP "notes": add_note / list_notes / search_notes (JSON)
  registry.py             # ServerSpec + реестр 4 серверов (абсолютные пути)
  client.py               # call_tool(spec, tool, args, python?, env?) через mcp.Client
  orchestrator.py         # parse_goal / route / run_flow + trace (ядро)
  server.py               # MCP "orchestrator": list_servers, plan, run_flow, call
  test_orchestrator.py    # pytest: роутер, trace, notes, stdio (офлайн)
  requirements.txt        # mcp>=2,<3 ; pytest>=8
  pyproject.toml
  .gitignore              # .venv/, __pycache__/, .pytest_cache/, notes.json, out/, video-script.html
  opencode.example.jsonc  # registraция orchestrator + notes
  README.md
  LESSON.md
  lesson.html
  video-script.html
docs/superpowers/specs/2026-09-28-day20-orchestration-design.md   # этот документ
```

### `notes_server.py` — новый MCP-сервер

- `MCPServer("notes")`; хранит заметки в JSON:
  `NOTES_DB` (env) или `day20/notes.json` по умолчанию.
- `add_note(title, body) -> {id, title, body, created_at}`
- `list_notes() -> {notes: [...]}`
- `search_notes(query) -> {query, matches: [...]}` (подстрока по title/body, регистронезависимо)
- Ошибки файла → `ValueError`.

### `registry.py`

- `ServerSpec(name, script: Path)` — dataclass.
- `SERVERS: dict[str, ServerSpec]` для `weather`, `compose`, `scheduler`, `notes`.
- Пути **абсолютные** (от `Path(__file__)`), чтобы работать из любого cwd.

### `client.py`

- `make_params(spec, python=None, env=None)` → `StdioServerParameters`:
  - по умолчанию `command=["uv","run","--no-project","--with","mcp>=2,<3", script]`;
  - если задан `python` — `command=[python, script]` (для тестов через venv).
- `call_tool(spec, tool, args, python=None, env=None) -> dict` (async) — открывает
  `mcp.Client`, вызывает инструмент, парсит JSON из ответа; `is_error` → `ClientError`.

### `orchestrator.py` — ядро

- `Step(server, tool, args: dict)` — dataclass; `as_dict()`.
- `parse_goal(goal) -> {topic, city, reminder}` — rule-based:
  - `city` — regex `(?:в|во)\s+([А-ЯЁ][а-яё-]+)`;
  - `reminder` — слово «напомн» в цели;
  - `topic` — текст после «про»/«о»/«об» либо вся цель без вводных слов.
- `route(topic, city=None, reminder=False, in_seconds=60, reminder_text=None) -> list[Step]`:
  порядок из флоу выше; `weather` — только при `city`; `reminder` — только при
  `reminder`. Последний шаг всегда `notes.add_note`.
- `run_flow(goal, caller=None, python=None) -> dict` (async):
  - `parse_goal` → `route` → исполнение шагов;
  - `caller(server, tool, args)` (async) инъектится в тестах; по умолчанию — реальный
    `client.call_tool` через `AsyncExitStack` (клиент на сервер);
  - контекст передаёт данные между шагами; `$key` резолвится из контекста;
  - ошибка шага → запись `{ok: false, error}` в trace и **останов** флоу
    (`ok=false` в отчёте, частичный trace сохранён);
  - возврат: `{goal, params, steps_planned, trace: [{index, server, tool, args, ok,
    result|error}], ok, error, output_path}`.

### `server.py` — MCP-сервер `orchestrator`

| Инструмент | Параметры | Возврат |
|---|---|---|
| `list_servers` | — | `{servers: [{name, script}]}` |
| `plan` | `goal: str` | `{goal, params, steps: [...]}` |
| `run_flow` | `goal: str` | отчёт с `trace` (см. выше) |
| `call` | `server, tool, args?` | результат прямого вызова инструмента на сервере |

`run_flow`/`call` — **async** (SDK v2 поддерживает async-инструменты). Доменные
ошибки → `ValueError`.

## Модель данных

Постоянного хранилища у оркестратора нет. Единственный файл — `day20/notes.json`
(заметки), путь переопределяется `NOTES_DB`; в `.gitignore`.

## Тесты (офлайн, детерминированно) — ориентир ≥12

`test_orchestrator.py`:

- `parse_goal`: тема/город/напоминание.
- `route`: полный порядок (weather→search→summarize→save→reminder→note); без города
  weather пропущен; без напоминания scheduler пропущен; note всегда последний.
- `run_flow` с фейковым async-`caller`:
  - order/trace: последовательность `(server, tool)` совпадает с планом;
  - передача данных: `summarize` получил `$search_text` из `search`, `add_note`
    получил `$summary` из `summarize`; `save` получил `$markdown`;
  - ошибка шага → `ok=false`, trace обрывается на месте ошибки.
- `notes`: add/list/search на временном JSON (`tmp_path`).
- stdio-интеграция:
  - `notes_server.py` как **отдельный** MCP-сервер: `add_note` → `search_notes` через
    `client.call_tool` (доказывает работу MCP-клиента оркестратора);
  - `day20/server.py` отдаёт 4 инструмента; `plan` через stdio возвращает шаги.

Запуск: `& ".venv\Scripts\python.exe" -m pytest -q`.

## Регистрация в opencode

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "orchestrator": {
      "type": "local",
      "command": ["uv", "run", "--no-project", "--with", "mcp>=2,<3", "server.py"],
      "cwd": "day20",
      "enabled": true,
      "timeout": 120000
    },
    "notes": {
      "type": "local",
      "command": ["uv", "run", "--no-project", "--with", "mcp>=2,<3", "notes_server.py"],
      "cwd": "day20",
      "enabled": true,
      "timeout": 60000
    }
  }
}
```

Плюс (как д18/19) запись в активный оверрайд с **абсолютными** путями. Отдельные
серверы `weather`/`scheduler`/`compose` уже зарегистрированы.

## Демонстрация (видео)

1. `opencode mcp list` → `✓ orchestrator`, `✓ notes`, `✓ weather`, `✓ scheduler`, `✓ compose`.
2. opencode: «Узнай погоду в Москве, найди в Википедии про Model Context Protocol,
   сохрани конспект и напомни проверить через минуту» →
   агент вызывает `orchestrator_run_flow`.
3. Показать `trace`: шаги по 4 серверам в правильном порядке, данные переданы.
4. Показать `orchestrator_plan` (последовательность до выполнения) и файлы:
   `day19/out/*.md`, напоминание в scheduler, заметку в `notes`.
5. `pytest -q` → все зелёные.

## Критерии готовности

- [ ] `notes_server.py`, `registry.py`, `client.py`, `orchestrator.py`, `server.py`.
- [ ] `pytest -q` зелёный (офлайн).
- [ ] Живой флоу проходит по инструментам 4 серверов (weather/compose/scheduler/notes).
- [ ] `plan` до выполнения = порядок в `trace` после выполнения.
- [ ] `day20/opencode.example.jsonc` регистрирует `orchestrator` + `notes`.
- [ ] В opencode агент запускает длинный флоу.
- [ ] Обновлены `README.md`, `LESSON.md`, `lesson.html`, `video-script.html`.
- [ ] Коммит и push в `origin/main`.

## Риски и заметки

- Запуск 4 серверов через `uv` на шаг медленный → в `run_flow` держим по одному
  клиенту на сервер (`AsyncExitStack`), а не поднимаем процесс на каждый шаг.
- Живой флоу требует сети (weather = wttr.in, compose = Wikipedia). В тестах — фейк.
- Rule-based `parse_goal` хрупок для сложных фраз — это осознанное упрощение;
  `route` принимает и типизированные параметры.
- Async-инструменты SDK v2: если `@mcp.tool()` async не поддержит — обернуть вызов
  фонового клиента; проверяется stdio-тестом.
- Кириллица: JSON-RPC в UTF-8; CLI-вывод через `$env:PYTHONIOENCODING="utf-8"`.
