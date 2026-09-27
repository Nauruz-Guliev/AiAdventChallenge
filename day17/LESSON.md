# Day 17 — Первый инструмент MCP (конспект)

День 16 дал протокол MCP: роли, транспорты, JSON-RPC, как поднять клиент и
подключить сервер к host. День 17 — следующий шаг: настоящий инструмент вокруг
**внешнего API**, который агент вызывает сам и использует его результат.

## Что делаем

MCP-сервер погоды с двумя инструментами — `get_weather` и `get_forecast` —
и подключение к агенту opencode.

## Инструмент: регистрация, параметры, результат

Сервер — `MCPServer("weather")`; инструмент регистрируется `@mcp.tool()`.
Параметры выводятся из сигнатуры и docstring, результат — возвращаемый `dict`.

```python
@mcp.tool()
def get_weather(city: str) -> dict:
    """Текущая погода в городе.

    Args:
        city: Название города, например "Москва".
    """
    place = weather_api.geocode(city)
    current = weather_api.current_weather(place.latitude, place.longitude)
    return {"city": place.name, **current}
```

- `city: str` → обязательный строковый аргумент;
- `days: int = 3` → необязательный, по умолчанию 3 (ограничен 1..3);
- ошибка `WeatherError` → `ValueError`, агент видит `isError` и сообщение;
- результат-`dict` сериализуется в JSON и отдаётся агенту.

```json
{"city": "Москва", "temperature_c": 13.0, "feels_like_c": 11.0,
 "humidity_percent": 67, "wind_kmh": 8.0, "weather": "Пасмурно"}
```

## Источник данных

```
город ──geocode──▶ (lat, lon) ──wttr.in──▶ погода
        Open-Meteo                    wttr.in (j1, lang=ru)
```

- `weather_api.geocode(city)` — Open-Meteo geocoding, `language=ru`;
- `current_weather` / `daily_forecast` — wttr.in по координатам;
- `_describe(entry)` — русский текст из `lang_ru`;
- HTTP через stdlib `urllib`; ошибки → `WeatherError`.

Почему не Open-Meteo целиком: хост `api.open-meteo.com` (погода) на этой сети
заблокирован, а геокодинг Open-Meteo и `wttr.in` — доступны.

## Подключение к opencode

Проектный конфиг в корне репозитория (`opencode.json`) — действует только здесь:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "weather": {
      "type": "local",
      "command": ["uv", "run", "--no-project", "--with", "mcp>=2,<3", "server.py"],
      "cwd": "day17",
      "enabled": true,
      "timeout": 60000
    }
  }
}
```

- `type: "local"` — opencode сам запускает процесс и говорит по stdio;
- `command` — массив «команда + аргументы» (`uv` подтянет `mcp`);
- путь — относительный корня воркспейса (проект) или **абсолютный** (глобальный
  конфиг), иначе сервер не найдёт `server.py` и упадёт;
- конфиг читается один раз при старте → **перезапустить opencode**;
- статус и команда: `opencode mcp list`.

## Как агент подхватывает инструмент

1. opencode при старте запускает сервер и забирает описание инструментов.
2. Модель видит **имя, описание и схему** (с префиксом сервера:
   `weather_get_weather`).
3. По запросу модель выбирает инструмент и аргументы:
   `weather_get_weather({"city": "Москва"})`.
4. Выполняет сервер (не модель): geocode → wttr.in.
5. Результат возвращается модели → она формулирует ответ.

```
Пользователь:  Какая сейчас погода в Москве?
LLM:           → weather_get_weather({"city": "Москва"})
Сервер:        {"temperature_c": 13.0, "weather": "Пасмурно", ...}
LLM:           В Москве сейчас 13 °C, пасмурно, ветер 8 км/ч.
```

## Проверка

```powershell
& ".venv\Scripts\python.exe" -m pytest -q   # 15 passed (офлайн)
```

## Упражнения

1. Инструмент `get_temperature(city)` — только температура.
2. Параметр `units` (`metric`/`imperial`).
3. Инструмент `compare(cities: list[str])` — сравнить города.
