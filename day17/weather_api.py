from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WTTR_URL = "https://wttr.in"
TIMEOUT_SECONDS = 20
USER_AGENT = "advent-mcp-weather/1.0"


class WeatherError(Exception):
    """Ошибка обращения к погодному API."""


@dataclass(frozen=True)
class Geocode:
    name: str
    latitude: float
    longitude: float


def _get_json(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}" if query else url
    request = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.URLError as exc:
        raise WeatherError(f"Сеть недоступна: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise WeatherError("Некорректный ответ API") from exc


def geocode(city: str) -> Geocode:
    data = _get_json(
        GEOCODE_URL, {"name": city, "count": 1, "language": "ru", "format": "json"}
    )
    results = data.get("results") or []
    if not results:
        raise WeatherError(f"Город не найден: {city}")
    first = results[0]
    return Geocode(
        name=first.get("name", city),
        latitude=float(first["latitude"]),
        longitude=float(first["longitude"]),
    )


def _describe(entry: dict) -> str:
    for key in ("lang_ru", "weatherDesc"):
        values = entry.get(key) or []
        if values:
            value = (values[0].get("value") or "").strip()
            if value:
                return value
    return "нет данных"


def _fetch_wttr(latitude: float, longitude: float) -> dict:
    return _get_json(
        f"{WTTR_URL}/{latitude},{longitude}", {"format": "j1", "lang": "ru"}
    )


def current_weather(latitude: float, longitude: float) -> dict:
    data = _fetch_wttr(latitude, longitude)
    conditions = data.get("current_condition") or []
    if not conditions:
        raise WeatherError("API не вернул текущую погоду")
    current = conditions[0]
    return {
        "temperature_c": float(current["temp_C"]),
        "feels_like_c": float(current["FeelsLikeC"]),
        "humidity_percent": int(current["humidity"]),
        "wind_kmh": float(current["windspeedKmph"]),
        "weather": _describe(current),
    }


def _day_description(hourly: list[dict]) -> str:
    for entry in hourly:
        if entry.get("time") == "1200":
            return _describe(entry)
    if hourly:
        return _describe(hourly[0])
    return "нет данных"


def daily_forecast(latitude: float, longitude: float, days: int) -> list[dict]:
    data = _fetch_wttr(latitude, longitude)
    weather_days = data.get("weather") or []
    if not weather_days:
        raise WeatherError("API не вернул прогноз")
    forecast = []
    for day in weather_days[:days]:
        hourly = day.get("hourly") or []
        precipitation = max(
            (int(entry.get("chanceofrain") or 0) for entry in hourly), default=0
        )
        forecast.append(
            {
                "date": day["date"],
                "temp_max_c": float(day["maxtempC"]),
                "temp_min_c": float(day["mintempC"]),
                "precipitation_probability": precipitation,
                "weather": _day_description(hourly),
            }
        )
    return forecast
