# Day 17 — Первый инструмент MCP: погода через Open-Meteo

## Цель

Реализовать настоящий MCP-инструмент вокруг внешнего API (Open-Meteo) и
подключить его к своему агенту — opencode, — чтобы агент сам вызывал инструмент
и использовал результат. Демонстрация: в opencode спрашиваем «какая погода в
Москве?», агент вызывает MCP-инструмент и отвечает.

## Вне-цели (YAGNI)

- Не трогаем глобальный конфиг `~/.config/opencode/opencode.json`. Подключение
  **только проектное** (`opencode.json` в корне этого репозитория) — MCP работает
  лишь внутри этого репозитория.
- Не пишем собственный LLM/агент — агентом выступает opencode.
- Не берём API с ключами/регистрацией (Open-Meteo — без ключа).
- Не добавляем новых зависимостей, кроме `mcp`/`pytest`. HTTP — через stdlib
  `urllib`.
- Не делаем remote-транспорт (HTTP/SSE) — только stdio.
- Не пишем UI.

## Архитектура

```
opencode (агент)
   │  tools/list + tools/call через stdio (JSON-RPC)
   ▼
day17/server.py  (MCP-сервер: get_weather, get_forecast)
   │  geocode / current / daily  (HTTP, без ключа)
   ▼
Open-Meteo API  (geocoding-api.open-meteo.com + api.open-meteo.com)
```

### Дерево `day17/`

```
day17/
  weather_api.py    # HTTP-клиент Open-Meteo (geocode, current, daily), stdlib urllib
  server.py         # MCP-сервер: get_weather, get_forecast
  test_weather.py   # pytest: unit (мок HTTP) + интеграция (stdio)
  requirements.txt  # mcp>=2,<3 ; pytest>=8
  pyproject.toml    # pythonpath=., testpaths=.
  .gitignore        # .venv/, __pycache__/, video-script.html и пр.
  README.md
  LESSON.md
  lesson.html
  video-script.html
opencode.json       # (в корне репозитория) регистрация MCP-сервера weather
```

### `weather_api.py` — чистый HTTP-клиент

Модуль без MCP, отдельно тестируемый. Внутри — `_get_json(url, params)` на
`urllib.request` с таймаутом (~10 с), User-Agent и разбором ошибок.

- `geocode(city: str) -> Geocode` (dataclass: `name`, `latitude`, `longitude`).
  GET `https://geocoding-api.open-meteo.com/v1/search` c `name`, `count=1`,
  `language=ru`, `format=json`. Если результатов нет → `WeatherError("город не найден: ...")`.
- `current_weather(lat, lon) -> dict`. GET `https://api.open-meteo.com/v1/forecast`
  c `current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code`,
  `timezone=auto`.
- `daily_forecast(lat, lon, days) -> list[dict]`. GET `.../v1/forecast` c
  `daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code`,
  `forecast_days=<days>`, `timezone=auto`.
- `describe_weather(code: int) -> str` — код WMO → русский текст («Ясно»,
  «Пасмурно», «Дождь» и т.д.).
- `WeatherError(Exception)` — сеть/HTTP/некорректный ответ/город не найден.

### `server.py` — MCP-сервер

`MCPServer("weather")`. Инструменты регистрируются декоратором `@mcp.tool()`;
описание параметров — из типизированной сигнатуры и docstring (MCP сам строит
`inputSchema`); результат — возвращаемый `dict` (попадает в `structuredContent`).

- `get_weather(city: str) -> dict` — geocode → current, возвращает:

  ```json
  {
    "city": "Москва",
    "latitude": 55.75,
    "longitude": 37.62,
    "temperature_c": -3.2,
    "feels_like_c": -7.0,
    "humidity_percent": 85,
    "wind_kmh": 12.4,
    "weather": "Пасмурно"
  }
  ```

- `get_forecast(city: str, days: int = 3) -> dict` — geocode → daily, возвращает:

  ```json
  {
    "city": "Москва",
    "days": [
      {"date": "2026-09-27", "temp_max_c": 4.1, "temp_min_c": -1.0,
       "precipitation_probability": 20, "weather": "Переменная облачность"}
    ]
  }
  ```

  Параметр `days` ограничивается диапазоном 1..7 (clamp).

- Ошибки `WeatherError` превращаются в `ValueError` с понятным текстом — SDK
  вернёт `isError` с сообщением, агент это увидит.
- `if __name__ == "__main__": mcp.run()` (stdio).

### `opencode.json` (корень репозитория) — регистрация

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "weather": {
      "type": "local",
      "command": [".venv\\Scripts\\python.exe", "server.py"],
      "cwd": "day17",
      "enabled": true
    }
  }
}
```

Только проектное подключение — действует исключительно при открытии opencode в
этом репозитории. Требуется предварительно создать `day17/.venv` и поставить
зависимости (шаг документируется в README).

Открытый вопрос реализации: убедиться, что opencode резолвит `command[0]`
относительно `cwd`; если нет — использовать абсолютный путь к python.exe либо
`python` из PATH. Проверка — `opencode mcp list` и реальный запрос.

### Поток данных

`opencode` → (stdio JSON-RPC `tools/call`) → `server.py.get_weather(city)` →
`weather_api.geocode` → `weather_api.current_weather` → `dict` →
`structuredContent` → opencode формулирует ответ.

## Тесты (офлайн, без сети)

`test_weather.py`:

- unit (`weather_api`, мокнутый `_get_json`/`urlopen`):
  - `geocode` возвращает координаты;
  - `current_weather` формирует dict с нужными полями;
  - `daily_forecast` формирует список нужной длины;
  - неизвестный город → `WeatherError`;
  - ошибка сети/HTTP → `WeatherError`;
  - `describe_weather` для нескольких WMO-кодов.
- интеграция (spawn `server.py` через `StdioServerParameters` с `sys.executable`):
  - `list_tools` == `{"get_weather", "get_forecast"}`;
  - схема `get_weather`: `required == ["city"]`, тип string;
  - схема `get_forecast`: есть `days`, значение по умолчанию 3.
- вызов инструмента (в процессе, с мокнутым `server.weather_api.*`):
  - `get_weather("Москва")` возвращает dict нужной формы;
  - `get_forecast("Москва", 99)` даёт `len(days) <= 7`.

Запуск: `& ".venv\Scripts\python.exe" -m pytest -q`.

## Демонстрация (видео)

1. Создать `day17/.venv`, установить зависимости.
2. (Опц.) `python server.py` — сервер слушает stdio.
3. Открыть opencode в этом репозитории → «Какая сейчас погода в Москве?» →
   агент вызывает `weather_get_weather` → отвечает.
4. «Какой прогноз на 3 дня в Алматы?» → `weather_get_forecast`.
5. Показать `opencode.json` как «регистрацию инструмента».

## Критерии готовности

- [ ] `day17/weather_api.py` и `day17/server.py` реализованы.
- [ ] `pytest -q` зелёный (офлайн).
- [ ] `opencode.json` в корне регистрирует `weather`; действует только в этом репозитории.
- [ ] В opencode агент вызывает `get_weather`/`get_forecast` и использует результат.
- [ ] Обновлены `README.md`, `LESSON.md`, `lesson.html`, `video-script.html`.
- [ ] Коммит и push в `origin/main`.

## Риски и заметки

- Имена инструментов в opencode префиксуются именем сервера:
  `weather_get_weather`, `weather_get_forecast`.
- Windows: python venv — `.venv\Scripts\python.exe`.
- Кириллица в ответах: JSON-RPC идёт в UTF-8, проблем нет.
- Без сети инструмент вернёт ошибку; тесты — офлайн с моками.
