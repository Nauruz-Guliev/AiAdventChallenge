# Day 20 — Оркестрация MCP (несколько серверов, длинный флоу)

Сервер-оркестратор **`orchestrator`** сам является **MCP-клиентом**: он ходит по
stdio в несколько других MCP-серверов, **выбирает нужные инструменты** под цель,
**маршрутизирует** вызовы и выполняет **длинный флоу**, возвращая `trace` —
доказательство выбора и порядка вызовов.

## Идея

День 19 — композиция **внутри** одного сервера. День 20 — оркестрация **между**
серверами. Один вызов `orchestrator_run_flow("…")` проходит по инструментам четырёх
серверов:

```
weather.get_weather(city)              (д17, если указан город)
  → compose.search(topic)              (д19)
  → compose.summarize($search_text)    (д19)
  → compose.save_to_file($markdown)    (д19)
  → scheduler.add_reminder(text, sec)  (д18, если просили напомнить)
  → notes.add_note(title, $summary)    (д20, новый сервер)
```

`orchestrator_plan(goal)` показывает выбранную последовательность **до** выполнения,
а `run_flow` возвращает `trace` — по записи на шаг: `{index, server, tool, args, ok,
result}`. Порядок в `plan` и в `trace` совпадает.

## Пул серверов

| Сервер | Откуда | Инструмент |
|---|---|---|
| `weather` | day17 | `get_weather(city)` |
| `compose` | day19 | `search`, `summarize`, `save_to_file` |
| `scheduler` | day18 | `add_reminder(text, in_seconds)` |
| `notes` | **day20 (новый)** | `add_note`, `list_notes`, `search_notes` |

## Структура

```
day20/
  notes_server.py         # MCP "notes": заметки в JSON (NOTES_DB / notes.json)
  registry.py             # ServerSpec + реестр 4 серверов (абсолютные пути)
  client.py               # call_tool(spec, tool, args) через mcp.Client (stdio)
  orchestrator.py         # parse_goal / route / run_flow + trace
  server.py               # MCP "orchestrator": list_servers, plan, run_flow, call
  test_orchestrator.py    # 12 офлайн-тестов (роутер, trace, notes, stdio)
  requirements.txt        # mcp>=2,<3 ; pytest>=8
  pyproject.toml
  opencode.example.jsonc  # orchestrator + notes → в корень как opencode.json
  README.md
  LESSON.md               # конспект урока
  lesson.html             # подробный урок (браузер)
  video-script.html       # сценарий видео (в .gitignore)
  notes.json              # заметки (в .gitignore)
```

## Инструменты оркестратора

| Инструмент | Параметры | Возврат |
|---|---|---|
| `list_servers` | — | `{servers: [{name, script}]}` |
| `plan` | `goal: str` | `{goal, params, steps: [{server, tool, args}]}` |
| `run_flow` | `goal: str` | `{goal, params, steps_planned, trace, ok, error, output_path}` |
| `call` | `server, tool, args?` | прямой результат инструмента |

В opencode префикс: `orchestrator_run_flow`, `orchestrator_plan` и т.д.

## Установка

```powershell
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
```

## Быстрая проверка (нужна сеть: wttr.in + Wikipedia)

```powershell
$env:PYTHONIOENCODING="utf-8"; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8
& ".venv\Scripts\python.exe" -c "import asyncio, json, orchestrator; print(json.dumps(asyncio.run(orchestrator.run_flow('Узнай погоду в Москве и найди про Model Context Protocol, напомни проверить')), ensure_ascii=False, indent=2))"
```

Результат: `ok: true`, `trace` по 4 серверам, файл в `day19/out/`, заметка в
`day20/notes.json`, напоминание в SQLite планировщика.

## Подключение к opencode

```powershell
Copy-Item day20\opencode.example.jsonc opencode.json
```

**Перезапусти opencode.** Серверы `weather`/`compose`/`scheduler` уже
зарегистрированы (дни 17–19). Проверь:

```powershell
& opencode mcp list
# ✓ orchestrator, ✓ notes, ✓ weather, ✓ scheduler, ✓ compose
```

В чате:

```
Узнай погоду в Москве, найди в Википедии про Model Context Protocol,
сохрани конспект и напомни проверить через минуту
```

Агент вызовет `orchestrator_run_flow` — длинный флоу по четырём серверам.

**Важно:** проектный `opencode.json` работает, когда opencode запущен **из корня
репозитория** (тогда `cwd: "day20"` разрешается). Из другой папки — глобальный
конфиг с **абсолютными** путями к `server.py`/`notes_server.py` и `cwd`. Симптом
ошибки — `ENOENT … uv_spawn 'uv'` (несуществующий рабочий каталог).

## Тесты

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
```

Ожидаемо: `12 passed`. Тесты офлайн: роутер (`parse_goal`/`route`), `run_flow` с
фейковым `caller` (порядок, передача данных, остановка при ошибке), заметки на
`tmp_path` и stdio-интеграция (реальный вызов `notes_server` как отдельного
MCP-сервера + список инструментов оркестратора).

## Материалы

- [`LESSON.md`](./LESSON.md) — конспект: оркестрация и маршрутизация.
- [`lesson.html`](./lesson.html) — подробный урок (открой в браузере).
