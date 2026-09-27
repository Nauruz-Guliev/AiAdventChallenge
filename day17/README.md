# Day 17 — Первый инструмент MCP: погода

MCP-сервер с двумя инструментами (**`get_weather`**, **`get_forecast`**) вокруг
внешнего API, подключённый к агенту **opencode**. Агент сам вызывает инструмент
и использует результат: спрашиваешь «какая погода в Москве?» — opencode дергает
`weather_get_weather` и отвечает.

## Идея

День 16 показал минимальный MCP (`add`/`echo`/`today`). Здесь инструмент
**настоящий**: ходит в интернет за реальными данными. Заодно — регистрация
инструмента, описание входных параметров и возврат результата.

## Источники данных

| Шаг | Сервис | Ключ |
|---|---|---|
| Геокодинг: город → координаты | Open-Meteo geocoding | не нужен |
| Погода: текущая + прогноз 3 дня | **wttr.in** по координатам | не нужен |

Почему не Open-Meteo целиком: на этой сети хост `api.open-meteo.com`
(текущая/прогноз) блокируется, а `geocoding-api.open-meteo.com` и `wttr.in` —
доступны. Описания на русском берём из поля `lang_ru` (wttr.in, `lang=ru`).

## Структура

```
day17/
  weather_api.py          # geocode (Open-Meteo) + current/daily (wttr.in)
  server.py               # MCP-сервер: get_weather, get_forecast
  test_weather.py         # 15 офлайн-тестов (моки + stdio)
  requirements.txt        # mcp>=2,<3 ; pytest>=8
  pyproject.toml
  opencode.example.jsonc  # образец конфига → скопировать в корень как opencode.json
  README.md
  LESSON.md               # конспект урока
  lesson.html             # подробный урок (браузер)
  video-script.html       # сценарий видео (в .gitignore)
```

## Установка

```powershell
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
```

## Быстрая проверка

```powershell
& ".venv\Scripts\python.exe" -c "import json, server; print(json.dumps(server.get_weather('Москва'), ensure_ascii=False, indent=2))"
```

Пример:

```json
{
  "city": "Москва",
  "latitude": 55.75204,
  "longitude": 37.61781,
  "temperature_c": 13.0,
  "feels_like_c": 11.0,
  "humidity_percent": 67,
  "wind_kmh": 8.0,
  "weather": "Пасмурно"
}
```

## Подключение к opencode (только этот репозиторий)

MCP регистрируется **проектным** конфигом — он действует лишь когда opencode
открыт в этом репозитории. Глобальный `~/.config/opencode/opencode.json` не
затрагивается.

1. Скопируй образец в корень репозитория:

   ```powershell
   Copy-Item day17\opencode.example.jsonc opencode.json
   ```

2. **Перезапусти opencode** (конфиг читается один раз при старте).

3. В чате:

   ```
   Какая сейчас погода в Москве? (используй weather)
   Какой прогноз на 3 дня в Алматы?
   ```

Содержимое `opencode.json`:

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

`uv` есть в PATH — он сам подтягивает `mcp`, поэтому путь к venv указывать не
нужно (конфиг портативный). Если предпочитаешь venv, замени `command` на
`[".venv\\Scripts\\python.exe", "server.py"]` и добавь `"cwd": "day17"`.

**Важно:** файл должен лежать в **корне репозитория** — opencode ищет проектный
конфиг в корне воркспейса, из подпапки `day17/` он не подхватится.

**Глобально** (для всех проектов) запись добавляется в
`~/.config/opencode/opencode.json`. В этом случае относительный путь не годится —
нужен **абсолютный** путь к серверу: `command: ["uv","run","--no-project",
"--with","mcp>=2,<3","C:/полный/путь/day17/server.py"]` (можно и абсолютный
`python.exe` venv).

## Инструменты

| Инструмент | Параметры | Возврат |
|---|---|---|
| `get_weather` | `city: str` | `{city, latitude, longitude, temperature_c, feels_like_c, humidity_percent, wind_kmh, weather}` |
| `get_forecast` | `city: str`, `days: int = 3` (1..3) | `{city, days: [{date, temp_max_c, temp_min_c, precipitation_probability, weather}]}` |

В opencode инструменты видны с префиксом сервера: `weather_get_weather`,
`weather_get_forecast`. Результат приходит как JSON (агент читает и использует).

## Тесты

```powershell
& ".venv\Scripts\python.exe" -m pytest -q
```

Ожидаемо: `15 passed`. Тесты офлайн: API мокается; интеграционный тест поднимает
сервер по stdio и проверяет список инструментов и схемы аргументов.

## Материалы

- [`LESSON.md`](./LESSON.md) — конспект: как устроен инструмент MCP.
- [`lesson.html`](./lesson.html) — подробный урок (открой в браузере).
