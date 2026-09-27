# Day 17 — Первый инструмент MCP (конспект)

## Что такое «инструмент MCP»

Инструмент (tool) — это функция, которую MCP-сервер объявляет агенту. Агент
видит её имя, описание и схему аргументов и может решить её вызвать. Ключевое:
**один инструмент = имя + описание + входные параметры + результат**.

## Три шага задания

### 1. Регистрация инструмента

```python
from mcp.server import MCPServer

mcp = MCPServer("weather")

@mcp.tool()
def get_weather(city: str) -> dict:
    """Текущая погода в городе."""
    ...
```

Декоратор `@mcp.tool()` регистрирует функцию. Имя инструмента — имя функции.
Сервер запускается по stdio: `mcp.run()`.

### 2. Описание входных параметров

Параметры описываются **типизированной сигнатурой** и **docstring**. MCP сам
строит из них JSON-схему (`inputSchema`):

```python
@mcp.tool()
def get_forecast(city: str, days: int = 3) -> dict:
    """Прогноз погоды.

    Args:
        city: Название города, например "Москва".
        days: Число дней, 1..3. По умолчанию 3.
    """
```

`city: str` → `{"type": "string"}`, `days: int = 3` →
`{"type": "integer", "default": 3}`. `city` обязателен, `days` — нет.
На проводе (в JSON) поле называется `inputSchema`, а в Python-объекте —
`tool.input_schema`.

### 3. Возврат результата

Возвращаем `dict` — структурированные данные:

```python
return {
    "city": place.name,
    "temperature_c": 13.0,
    "weather": "Пасмурно",
    "latitude": place.latitude,
    "longitude": place.longitude,
    **current,
}
```

Ошибки превращаем в понятные: `WeatherError` → `ValueError`, SDK вернёт
`isError: true` с текстом, агент это увидит.

## Откуда данные

```
город ──geocode──▶ (lat, lon) ──wttr.in──▶ текущая погода / прогноз
        Open-Meteo                    wttr.in (format=j1, lang=ru)
```

- `weather_api.geocode(city)` — Open-Meteo geocoding, `language=ru`.
- `weather_api.current_weather(lat, lon)` — wttr.in `current_condition[0]`.
- `weather_api.daily_forecast(lat, lon, days)` — wttr.in `weather[]`.
- `_describe(entry)` — русский текст из `lang_ru`, иначе из `weatherDesc`.

Все HTTP-запросы — через stdlib `urllib` (ни одной лишней зависимости),
таймаут 20 c, ошибки → `WeatherError`.

## Как opencode подключает инструмент

Проектный конфиг `opencode.json` в корне репозитория:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "weather": {
      "type": "local",
      "command": ["uv", "run", "--directory", "day17", "--with", "mcp>=2,<3", "server.py"],
      "enabled": true,
      "timeout": 60000
    }
  }
}
```

- `type: "local"` — opencode запускает процесс и общается по **stdio**.
- `command` — массив: команда + аргументы (uv сам ставит `mcp`).
- Такой конфиг действует **только** для этого репозитория; глобальный не трогаем.

Под капотом opencode делает ровно то же, что клиент из дня 16:
`initialize` → `tools/list` → `tools/call`. Имена инструментов получают префикс
сервера: `weather_get_weather`, `weather_get_forecast`.

### Транскрипт на проводе (упрощённо)

Запрос списка (opencode → сервер):

```json
{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

Ответ (сервер → opencode), сокращённо:

```json
{"jsonrpc":"2.0","id":1,"result":{"tools":[
  {"name":"get_weather","description":"Текущая погода в городе.",
   "inputSchema":{"type":"object",
     "properties":{"city":{"type":"string"}},"required":["city"]}},
  {"name":"get_forecast","description":"Прогноз погоды на несколько дней.",
   "inputSchema":{"type":"object","properties":{
     "city":{"type":"string"},"days":{"type":"integer","default":3}},
     "required":["city"]}}
]}}
```

Вызов (opencode → сервер):

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call",
 "params":{"name":"get_weather","arguments":{"city":"Москва"}}}
```

Результат (сервер → opencode):

```json
{"jsonrpc":"2.0","id":2,"result":{
  "content":[{"type":"text","text":"{\"city\":\"Москва\",\"temperature_c\":13.0,\"weather\":\"Пасмурно\", ...}"}],
  "isError":false
}}
```

## Проверка

```powershell
& ".venv\Scripts\python.exe" -m pytest -q   # 15 passed (офлайн)
```

## Упражнения

1. Добавь инструмент `get_weather_only_temp(city)` → только температура.
2. Добавь параметр `units` (`metric`/`imperial`) в `get_weather`.
3. Ограничь `days` через аннотацию `Literal[1,2,3]` и посмотри, как изменится схема.
4. Сделай инструмент `compare(cities: list[str])` — сравни погоду в нескольких городах.

## Ошибки, на которые наступали

- `api.open-meteo.com` может быть заблокирован сетью → взяли wttr.in.
- Относительный путь к exe в конфиге на Windows резолвится не всегда → тут
  используем `uv` (в PATH), чтобы не зависеть от пути к venv.
- `tool.input_schema` (Python) vs `inputSchema` (JSON) — легко перепутать.
