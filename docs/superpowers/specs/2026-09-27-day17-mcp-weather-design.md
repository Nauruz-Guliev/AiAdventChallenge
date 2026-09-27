# Day 17 — Первый инструмент MCP: погода (Open-Meteo + wttr.in)

## Цель

Реализовать настоящий MCP-инструмент вокруг внешнего API и подключить его к
своему агенту — opencode, — чтобы агент сам вызывал инструмент и использовал
результат. Демонстрация: в opencode спрашиваем «какая погода в Москве?», агент
вызывает MCP-инструмент и отвечает.

## Вне-цели (YAGNI)

- Не трогаем глобальный конфиг `~/.config/opencode/opencode.json`. Подключение
  **только проектное** — `opencode.json` в корне этого репозитория.
- Не пишем собственный LLM/агент — агентом выступает opencode.
- Не берём API с ключами/регистрацией.
- Не добавляем новых зависимостей, кроме `mcp`/`pytest`. HTTP — через stdlib
  `urllib`.
- Не делаем remote-транспорт (HTTP/SSE) — только stdio.
- Не пишем UI.

## Изменения по ходу (важно)

- Изначально погода бралась целиком из Open-Meteo. На этой сети
  `api.open-meteo.com` (текущая/прогноз) **блокируется** — TCP 443 не проходит.
  `geocoding-api.open-meteo.com` при этом **работает**.
- Поэтому: **геокодинг** (город → координаты) — Open-Meteo (работает, точный,
  русские названия); **сама погода** (текущая + прогноз) — **wttr.in** по
  координатам (`https://wttr.in/{lat},{lon}?format=j1&lang=ru`), бесплатно и без
  ключа, доступен на этой сети. Русские описания берём из поля `lang_ru`.
- Прогноз wttr.in даёт на 3 дня → параметр `days` ограничен диапазоном 1..3.
- Файл `opencode.json` в корне harness не даёт создать автоматически (secret
  guard). Поэтому в репозитории лежит `day17/opencode.example.jsonc`, а в корень
  его копирует пользователь.

## Архитектура

```
opencode (агент)
   │  tools/list + tools/call через stdio (JSON-RPC)
   ▼
day17/server.py  (MCP-сервер: get_weather, get_forecast)
   │  geocode: Open-Meteo geocoding   │  current/daily: wttr.in
   ▼
geocoding-api.open-meteo.com          wttr.in
```

### Дерево `day17/`

```
day17/
  weather_api.py          # клиент: geocode (Open-Meteo) + current/daily (wttr.in)
  server.py               # MCP-сервер: get_weather, get_forecast
  test_weather.py         # pytest: 15 офлайн-тестов (моки + stdio-интеграция)
  requirements.txt        # mcp>=2,<3 ; pytest>=8
  pyproject.toml          # pythonpath=., testpaths=.
  .gitignore              # .venv/, __pycache__/, .pytest_cache/, video-script.html
  opencode.example.jsonc  # образец проектного конфига для копирования в корень
  README.md
  LESSON.md
  lesson.html
  video-script.html
opencode.json             # (в корне, создаёт пользователь) регистрация weather
```

### `weather_api.py` — клиент API

- `geocode(city) -> Geocode(name, latitude, longitude)` — Open-Meteo geocoding
  (`language=ru`); город не найден → `WeatherError`.
- `_fetch_wttr(lat, lon) -> dict` — GET `https://wttr.in/{lat},{lon}?format=j1&lang=ru`.
- `current_weather(lat, lon) -> dict` — из `current_condition[0]`:
  `temperature_c, feels_like_c, humidity_percent, wind_kmh, weather`.
- `daily_forecast(lat, lon, days) -> list[dict]` — из `weather[:days]`:
  `date, temp_max_c, temp_min_c, precipitation_probability` (max `chanceofrain`
  за день), `weather` (описание за 12:00).
- `_describe(entry)` — русский текст из `lang_ru`, иначе из `weatherDesc`.
- `_get_json(url, params)` — stdlib `urllib`, таймаут 20 c, ошибки → `WeatherError`.

### `server.py` — MCP-сервер

`MCPServer("weather")`. Регистрация — `@mcp.tool()`; параметры — из сигнатуры и
docstring (MCP строит `inputSchema`); результат — `dict`.

- `get_weather(city: str) -> dict` — geocode → current:

  ```json
  {"city": "Москва", "latitude": 55.752, "longitude": 37.618,
   "temperature_c": 13.0, "feels_like_c": 11.0, "humidity_percent": 67,
   "wind_kmh": 8.0, "weather": "Пасмурно"}
  ```

- `get_forecast(city: str, days: int = 3) -> dict` — geocode → daily (days 1..3):

  ```json
  {"city": "Алматы", "days": [
    {"date": "2026-09-28", "temp_max_c": 18.0, "temp_min_c": 10.0,
     "precipitation_probability": 9, "weather": "Пасмурно"}]}
  ```

- Ошибки `WeatherError` → `ValueError` (SDK вернёт `isError`).
- Возврат `dict` попадает в результат как сериализованный JSON в
  `content[0].text` (structuredContent SDK для `dict` не формирует) — агент
  читает текст и использует.

### `opencode.json` (корень репозитория) — регистрация

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "weather": {
      "type": "local",
      "command": ["uv", "run", "--no-project", "--directory", "day17",
                  "--with", "mcp>=2,<3", "server.py"],
      "enabled": true,
      "timeout": 60000
    }
  }
}
```

`uv` (0.11.28) есть в PATH — не зависим от пути к venv, конфиг портативный.
Проверено: `uv run --directory day17 --with mcp>=2,<3 server.py` поднимает сервер,
`tools/list` → `get_weather`, `get_forecast`; `tools/call get_weather` возвращает
реальные данные.

## Тесты (офлайн, без сети) — 15

`test_weather.py`: `_describe` (русский/фолбэк), `geocode` (координаты/не найдено/
ошибка), `current_weather` (форма/пустой ответ), `daily_forecast` (форма/пустой
ответ), `get_weather`/`get_forecast` в процессе (мок `weather_api`: форма, clamp
days → 3, `ValueError`), интеграция по stdio (2 инструмента, схема `city`
обязателен, `days` по умолчанию 3). Запуск: `& ".venv\Scripts\python.exe" -m pytest -q`.

## Демонстрация (видео)

1. `day17/.venv` + зависимости (или `uv run`, он сам подтянет mcp).
2. Показать `server.py`: регистрация (`@mcp.tool()`), параметры, результат.
3. Скопировать `day17/opencode.example.jsonc` → `opencode.json` в корне;
   перезапустить opencode.
4. В opencode: «Какая сейчас погода в Москве?» → агент вызывает
   `weather_get_weather` → отвечает.
5. «Какой прогноз на 3 дня в Алматы?» → `weather_get_forecast`.
6. `pytest -q` → 15 passed.

## Критерии готовности

- [x] `weather_api.py`, `server.py` реализованы.
- [x] `pytest -q` зелёный (15 passed, офлайн).
- [x] Живой вызов работает (Москва/Алматы).
- [ ] `opencode.json` в корне регистрирует `weather` (создаёт пользователь из
      `day17/opencode.example.jsonc`).
- [ ] В opencode агент вызывает `get_weather`/`get_forecast`.
- [ ] Обновлены `README.md`, `LESSON.md`, `lesson.html`, `video-script.html`.
- [ ] Коммит и push в `origin/main`.

## Риски и заметки

- `api.open-meteo.com` заблокирован на этой сети → используем wttr.in.
- wttr.in может отдавать rate-limit при частых запросах → инструмент вернёт
  `WeatherError`/`isError`; для демо это редкость.
- Имена инструментов в opencode префиксуются именем сервера:
  `weather_get_weather`, `weather_get_forecast`.
- Кириллица: JSON-RPC в UTF-8; описания на русском из `lang_ru`.
