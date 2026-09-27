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
  client.py       # клиент: stdio-подключение + list_tools (+ опц. вызов)
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

# с полной JSON-схемой аргументов
& ".venv\Scripts\python.exe" client.py --schema

# без цветов (если терминал не поддерживает ANSI)
& ".venv\Scripts\python.exe" client.py --plain

# дополнительно вызвать инструмент add
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
```

С флагом `--call-add` в конце печатается `Вызов add(2, 3) -> 5`.

## Проверка

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
```

Ожидаемо: `4 passed`. Тест сам поднимает сервер как подпроцесс, выполняет
handshake, проверяет список инструментов и формат вывода.

## Транспорт

Используется **stdio**: клиент запускает `server.py` как подпроцесс и
обменивается JSON-RPC через stdin/stdout. Никаких портов и внешних сервисов.
