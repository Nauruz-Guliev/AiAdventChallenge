# Day 16 — Подключение MCP

Минимальный пример: MCP-сервер с тремя инструментами и клиент, который
подключается к нему по stdio и выводит список доступных инструментов.

## Что такое MCP

MCP (Model Context Protocol) — стандарт, по которому LLM-приложение получает
доступ к внешним инструментам и данным. Сервер объявляет инструменты (имя,
описание, входную JSON-схему), клиент их запрашивает. Подробный разбор — в
[`LESSON.md`](./LESSON.md).

## Структура

```
day16/
  server.py       # MCP-сервер: инструменты add, echo, today
  client.py       # клиент: stdio-подключение + list_tools (+ опц. вызов)
  test_mcp.py     # автопроверка: соединение и список инструментов
  requirements.txt
  README.md
  LESSON.md       # отдельный урок «как это работает»
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

# дополнительно вызвать инструмент add
& ".venv\Scripts\python.exe" client.py --call-add 2 3
```

Ожидаемо: `MCP вернул инструментов: 3` и описания инструментов `add`, `echo`,
`today` с их `input_schema`. С флагом `--call-add` в конце печатается
`add(2, 3) = {'result': 5}`.

## Проверка

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
```

Ожидаемо: `3 passed`. Тест сам поднимает сервер как подпроцесс, выполняет
handshake и проверяет список инструментов.

## Транспорт

Используется **stdio**: клиент запускает `server.py` как подпроцесс и
обменивается JSON-RPC через stdin/stdout. Никаких портов и внешних сервисов.
