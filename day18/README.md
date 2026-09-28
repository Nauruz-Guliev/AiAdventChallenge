# Day 18 — Планировщик и фоновые задачи

MCP-инструмент с **отложенным и периодическим** выполнением: агент ставит
напоминания и задачи сбора, отдельный **демон** выполняет их по расписанию
**24/7**, всё состояние — в **SQLite**, а инструмент отдаёт **агрегированную
сводку**. Сборщик собирает погоду, переиспользуя `day17/weather_api.py`.

## Идея

День 17 — инструмент, который отвечает на запрос. День 18 — инструмент, который
работает **во времени**: помнит задачи, тикает и копит данные, пока агент закрыт,
и отдаёт сводку при следующем обращении.

Ключевая вещь: MCP — **pull-модель**, сервер не может сам «толкнуть» сообщение
агенту. Поэтому «периодически выдаёт сводку» = демон по расписанию
**материализует** сводки в БД, а агент читает их через инструмент.

## Архитектура

```
opencode (агент)
   │  stdio / JSON-RPC
   ▼
day18/server.py   (MCP: планирование + чтение агрегатов) ─┐
                                                           ├─► day18/state.db (SQLite)
day18/worker.py   (демон: тикает раз в секунду, выполняет) ┘
   │
   ▼  sources.sample_weather(city)
day17/weather_api.py  →  wttr.in
```

Два процесса, **одна общая БД**. Вся логика и SQL — в `scheduler.py` (чистые
функции), её используют и демон, и сервер, и тесты.

## Структура

```
day18/
  scheduler.py            # ядро: схема/CRUD/due/агрегация (без процессов)
  sources.py              # источник: sample_weather() через day17
  worker.py               # демон: asyncio-тик раз в секунду
  server.py               # MCP-сервер "scheduler": 8 инструментов
  test_scheduler.py       # 19 офлайн-тестов (ядро + воркер + stdio)
  requirements.txt        # mcp>=2,<3 ; pytest>=8
  pyproject.toml
  opencode.example.jsonc  # образец конфига → скопировать в корень как opencode.json
  README.md
  LESSON.md               # конспект урока
  lesson.html             # подробный урок (браузер)
  video-script.html       # сценарий видео (в .gitignore)
  state.db                # БД (создаётся автоматически, в .gitignore)
```

## Установка

```powershell
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
```

## Запуск демона (24/7)

В **отдельном** терминале (его opencode не поднимает):

```powershell
& ".venv\Scripts\python.exe" day18\worker.py
# [worker] запущен, БД: ...\day18\state.db, тик 1 c
```

Остановить — `Ctrl+C`. Демон и MCP-сервер должны смотреть в **одну и ту же** БД; по
умолчанию это `day18/state.db` (путь считается от `scheduler.py`, не от cwd).
Переопределить — переменной окружения `SCHEDULER_DB`.

## Подключение к opencode (только этот репозиторий)

1. Скопируй образец в корень репозитория:

   ```powershell
   Copy-Item day18\opencode.example.jsonc opencode.json
   ```

2. **Перезапусти opencode** (конфиг читается один раз при старте).

3. В чате:

   ```
   Поставь напоминание "перерыв" через 20 секунд.
   Начни собирать погоду в Москве каждые 30 секунд и делай сводку каждые 60 секунд.
   Покажи последнюю сводку.
   ```

Содержимое `opencode.json`:

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

**Важно:** проектный `opencode.json` работает, только когда opencode запущен
**из корня репозитория** (тогда `cwd: "day18"` разрешается). Если запускаешь
opencode из другой папки — правь **глобальный** конфиг и указывай **абсолютные**
пути и к `server.py`, и к `cwd`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "scheduler": {
      "type": "local",
      "command": ["uv", "run", "--no-project", "--with", "mcp>=2,<3",
                  "C:/Users/Nauruz-work/Documents/ai_advent_challenge/day18/server.py"],
      "cwd": "C:/Users/Nauruz-work/Documents/ai_advent_challenge/day18",
      "enabled": true,
      "timeout": 60000
    }
  }
}
```

<div>

**Симптом ошибки:** `opencode mcp list` → `✗ scheduler failed` с
`ENOENT … uv_spawn 'uv'`, хотя `uv` установлен. Причина — **несуществующий рабочий
каталог**: относительный `cwd: "day18"` считается от папки запуска opencode. Лечится
абсолютным `cwd` (см. выше) либо запуском opencode из корня репозитория.

</div>

## Инструменты (8)

| Инструмент | Параметры | Что делает |
|---|---|---|
| `add_reminder` | `text: str`, `in_seconds: int` | разовое напоминание через N c |
| `list_reminders` | — | активные + недавно сработавшие |
| `cancel` | `task_id: int` | выключить задачу |
| `start_collection` | `city: str`, `every_seconds: int` | периодический сбор погоды |
| `start_summary` | `city: str`, `every_seconds: int`, `window_seconds: int` | периодическая сводка |
| `collect_now` | `city: str` | внеплановый замер сейчас |
| `get_summary` | `city: str`, `period_seconds: int` | агрегат по сырым замерам за окно |
| `latest_summary` | `city: str \| None = None` | последняя материализованная сводка |

В opencode имена с префиксом сервера: `scheduler_add_reminder` и т.д.

## Как это выглядит в работе

1. Демон запущен в терминале A и тикает.
2. В opencode агент вызывает `start_collection("Москва", 30)` и
   `start_summary("Москва", 60, 3600)`.
3. **Закрываешь opencode** — демон продолжает писать замеры в `samples`.
4. Открываешь снова → `latest_summary`/`get_summary` → агент выдаёт сводку
   (среднее/мин/макс температуры за период).

## Тесты

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
```

Ожидаемо: `19 passed`. Тесты офлайн: источник мокается; интеграционный тест
поднимает MCP-сервер по stdio и проверяет 8 инструментов и вызовы.

## Материалы

- [`LESSON.md`](./LESSON.md) — конспект: почему pull, два процесса, тик, агрегация.
- [`lesson.html`](./lesson.html) — подробный урок (открой в браузере).
- [`video-script.html`](./video-script.html) — пошаговый сценарий видео.
