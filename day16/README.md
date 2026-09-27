# Day 16 — Подключение MCP

Минимальный пример: MCP-сервер с тремя инструментами и клиент, который
подключается к нему по stdio и выводит список доступных инструментов.

## Что такое MCP

MCP (Model Context Protocol) — стандарт, по которому LLM-приложение получает
доступ к внешним инструментам и данным. Сервер объявляет инструменты (имя,
описание, входную JSON-схему), клиент их запрашивает.

## Материалы

- **[`lesson.html`](./lesson.html)** — подробный урок (открой в браузере): зачем
  MCP, роли, примитивы, транспорты, JSON-RPC на проводе, разбор кода, настройка
  в реальных host'ах, ошибки, упражнения.
- [`LESSON.md`](./LESSON.md) — тот же материал кратко, конспектом (для GitHub).

## Структура

```
day16/
  server.py       # MCP-сервер: инструменты add, echo, today
  client.py       # клиент: stdio-подключение + list_tools + интерактивный режим
  test_mcp.py     # автопроверка: соединение и список инструментов
  lesson.html     # подробный урок (браузер)
  LESSON.md       # конспект урока (markdown)
  requirements.txt
  README.md
  video-script.html  # сценарий видео (в .gitignore)
```

## Установка

```powershell
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
```

## Запуск

```powershell
# подключиться и вывести список инструментов
& ".venv\Scripts\python.exe" client.py

# интерактивный режим: вызывать инструменты в одной живой сессии
& ".venv\Scripts\python.exe" client.py -i

# с полной JSON-схемой аргументов
& ".venv\Scripts\python.exe" client.py --schema

# без цветов (если терминал не поддерживает ANSI)
& ".venv\Scripts\python.exe" client.py --plain

# разово вызвать инструмент add
& ".venv\Scripts\python.exe" client.py --call-add 2 3
```

Пример вывода:

```
============================================================
  MCP: подключение и список инструментов
  транспорт: stdio
============================================================

[OK] Соединение установлено. Инструментов: 3

[1] add
    Описание: Add two numbers.
    Аргументы:
      - a: integer (обязательный)
      - b: integer (обязательный)

[2] echo
    Описание: Return the given text unchanged.
    Аргументы:
      - text: string (обязательный)

[3] today
    Описание: Return today's date in ISO format (YYYY-MM-DD).
    Аргументы: нет

Подсказка: запусти с -i для интерактивного режима.
```

## Интерактивный режим

`-i` открывает **одно** соединение и не закрывает его: список инструментов
печатается один раз, дальше их можно вызывать подряд. Аргументы — позиционно,
по порядку из схемы; результат печатается как JSON, который MCP отдаёт наружу
(`content` + `structuredContent`).

```
mcp> add 2 3
Результат (как MCP отдаёт):
{
  "content": [ { "type": "text", "text": "5" } ],
  "structuredContent": { "result": 5 },
  "isError": false,
  "resultType": "complete"
}

mcp> echo "два слова"
Результат (как MCP отдаёт):
{ ... "structuredContent": { "result": "два слова" } ... }

mcp> today
mcp> help add        # справка и схема по конкретному инструменту
mcp> tools           # показать список инструментов заново
mcp> quit            # выход (или Ctrl+C)
```

При неверных аргументах печатается понятная подсказка с форматом:
`Ошибка аргументов: аргумент 'a': ожидалось integer, получено 'x'`.

## Проверка

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
```

Ожидаемо: `10 passed`. Тесты поднимают сервер как подпроцесс, выполняют
handshake, проверяют список инструментов, формат вывода и разбор аргументов
(`parse_input`, `bind_positional`, `format_result`).

## Транспорт

Используется **stdio**: клиент запускает `server.py` как подпроцесс и
обменивается JSON-RPC через stdin/stdout. Никаких портов и внешних сервисов.
