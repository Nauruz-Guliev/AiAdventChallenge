from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 10
USER_AGENT = "advent-mcp-weather/1.0"

WMO_DESCRIPTIONS = {
    0: "Ясно",
    1: "Преимущественно ясно",
    2: "Переменная облачность",
    3: "Пасмурно",
    45: "Туман",
    48: "Изморозь",
    51: "Слабая морось",
    53: "Морось",
    55: "Сильная морось",
    56: "Слабая ледяная морось",
    57: "Ледяная морось",
    61: "Небольшой дождь",
    63: "Дождь",
    65: "Сильный дождь",
    66: "Слабый ледяной дождь",
    67: "Ледяной дождь",
    71: "Небольшой снег",
    73: "Снег",
    75: "Сильный снег",
    77: "Снежная крупа",
    80: "Небольшие ливни",
    81: "Ливни",
    82: "Сильные ливни",
    85: "Небольшой снегопад",
    86: "Сильный снегопад",
    95: "Гроза",
    96: "Гроза с градом",
    99: "Сильная гроза с градом",
}


class WeatherError(Exception):
    """Ошибка обращения к погодному API."""


@dataclass(frozen=True)
class Geocode:
    name: str
    latitude: float
    longitude: float


def describe_weather(code: int) -> str:
    return WMO_DESCRIPTIONS.get(code, f"Код погоды {code}")


def _get_json(url: str, params: dict) -> dict:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
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


def current_weather(latitude: float, longitude: float) -> dict:
    data = _get_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,apparent_temperature,"
                "relative_humidity_2m,wind_speed_10m,weather_code"
            ),
            "timezone": "auto",
        },
    )
    current = data.get("current")
    if not current:
        raise WeatherError("API не вернул текущую погоду")
    return {
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "wind_kmh": current.get("wind_speed_10m"),
        "weather": describe_weather(int(current.get("weather_code", -1))),
    }


def daily_forecast(latitude: float, longitude: float, days: int) -> list[dict]:
    data = _get_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": (
                "temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max,weather_code"
            ),
            "forecast_days": days,
            "timezone": "auto",
        },
    )
    daily = data.get("daily") or {}
    dates = daily.get("time") or []
    if not dates:
        raise WeatherError("API не вернул прогноз")
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    precipitation = daily.get("precipitation_probability_max") or []
    codes = daily.get("weather_code") or []
    forecast = []
    for index, day in enumerate(dates):
        code = codes[index] if index < len(codes) else None
        forecast.append(
            {
                "date": day,
                "temp_max_c": highs[index] if index < len(highs) else None,
                "temp_min_c": lows[index] if index < len(lows) else None,
                "precipitation_probability": (
                    precipitation[index] if index < len(precipitation) else None
                ),
                "weather": (
                    describe_weather(int(code)) if code is not None else "нет данных"
                ),
            }
        )
    return forecast
