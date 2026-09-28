"""Источник данных для сборщика: замер погоды через day17."""
from __future__ import annotations

import sys
from pathlib import Path


class SourceError(RuntimeError):
    """Источник не смог отдать данные (сеть, неизвестный город, лимит)."""


_DAY17 = Path(__file__).resolve().parent.parent / "day17"
if str(_DAY17) not in sys.path:
    sys.path.insert(0, str(_DAY17))


def sample_weather(city: str) -> dict:
    import weather_api

    try:
        place = weather_api.geocode(city)
        current = weather_api.current_weather(place.latitude, place.longitude)
    except weather_api.WeatherError as exc:
        raise SourceError(str(exc)) from exc
    return {"temperature_c": current["temperature_c"], "weather": current["weather"]}
