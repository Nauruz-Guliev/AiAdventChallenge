import asyncio
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

import server
import weather_api
from weather_api import WeatherError

SERVER_SCRIPT = Path(__file__).with_name("server.py")


def server_params():
    return StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])


async def list_tools():
    async with Client(server_params()) as client:
        return (await client.list_tools()).tools


def test_describe_prefers_russian():
    entry = {"lang_ru": [{"value": "  Ясно "}], "weatherDesc": [{"value": "Sunny"}]}
    assert weather_api._describe(entry) == "Ясно"


def test_describe_falls_back_to_english():
    assert weather_api._describe({"weatherDesc": [{"value": "Sunny"}]}) == "Sunny"


def test_geocode_returns_coordinates(monkeypatch):
    monkeypatch.setattr(
        weather_api,
        "_get_json",
        lambda url, params: {
            "results": [{"name": "Москва", "latitude": 55.75, "longitude": 37.62}]
        },
    )
    place = weather_api.geocode("Москва")
    assert place.name == "Москва"
    assert place.latitude == 55.75
    assert place.longitude == 37.62


def test_geocode_unknown_city(monkeypatch):
    monkeypatch.setattr(weather_api, "_get_json", lambda url, params: {"results": []})
    with pytest.raises(WeatherError):
        weather_api.geocode("Атлантида")


def test_geocode_propagates_network_error(monkeypatch):
    def boom(url, params):
        raise WeatherError("Сеть недоступна")

    monkeypatch.setattr(weather_api, "_get_json", boom)
    with pytest.raises(WeatherError):
        weather_api.geocode("Москва")


def test_current_weather_shape(monkeypatch):
    monkeypatch.setattr(
        weather_api,
        "_get_json",
        lambda url, params: {
            "current_condition": [
                {
                    "temp_C": "13",
                    "FeelsLikeC": "11",
                    "humidity": "67",
                    "windspeedKmph": "8",
                    "weatherCode": "122",
                    "weatherDesc": [{"value": "Overcast"}],
                    "lang_ru": [{"value": "Пасмурно"}],
                }
            ]
        },
    )
    result = weather_api.current_weather(55.75, 37.62)
    assert result == {
        "temperature_c": 13.0,
        "feels_like_c": 11.0,
        "humidity_percent": 67,
        "wind_kmh": 8.0,
        "weather": "Пасмурно",
    }


def test_current_weather_missing_data(monkeypatch):
    monkeypatch.setattr(weather_api, "_get_json", lambda url, params: {})
    with pytest.raises(WeatherError):
        weather_api.current_weather(55.75, 37.62)


def test_daily_forecast_shape(monkeypatch):
    monkeypatch.setattr(
        weather_api,
        "_get_json",
        lambda url, params: {
            "weather": [
                {
                    "date": "2026-09-27",
                    "maxtempC": "17",
                    "mintempC": "11",
                    "hourly": [
                        {"time": "0", "chanceofrain": "5",
                         "weatherDesc": [{"value": "Cloudy"}]},
                        {"time": "1200", "chanceofrain": "20",
                         "lang_ru": [{"value": "Переменная облачность"}],
                         "weatherDesc": [{"value": "Partly cloudy"}]},
                        {"time": "1500", "chanceofrain": "10"},
                    ],
                }
            ]
        },
    )
    result = weather_api.daily_forecast(55.75, 37.62, 1)
    assert len(result) == 1
    assert result[0] == {
        "date": "2026-09-27",
        "temp_max_c": 17.0,
        "temp_min_c": 11.0,
        "precipitation_probability": 20,
        "weather": "Переменная облачность",
    }


def test_daily_forecast_missing_data(monkeypatch):
    monkeypatch.setattr(weather_api, "_get_json", lambda url, params: {"weather": []})
    with pytest.raises(WeatherError):
        weather_api.daily_forecast(55.75, 37.62, 3)


def test_get_weather_uses_api(monkeypatch):
    monkeypatch.setattr(
        server.weather_api,
        "geocode",
        lambda city: weather_api.Geocode("Москва", 55.75, 37.62),
    )
    monkeypatch.setattr(
        server.weather_api,
        "current_weather",
        lambda lat, lon: {
            "temperature_c": 13.0,
            "feels_like_c": 11.0,
            "humidity_percent": 67,
            "wind_kmh": 8.0,
            "weather": "Пасмурно",
        },
    )
    result = server.get_weather("Москва")
    assert result["city"] == "Москва"
    assert result["temperature_c"] == 13.0
    assert result["weather"] == "Пасмурно"


def test_get_forecast_clamps_days(monkeypatch):
    captured = {}

    def fake_geocode(city):
        return weather_api.Geocode(city, 0.0, 0.0)

    def fake_forecast(lat, lon, days):
        captured["days"] = days
        return [
            {
                "date": f"2026-09-{27 + i}",
                "temp_max_c": 0.0,
                "temp_min_c": 0.0,
                "precipitation_probability": 0,
                "weather": "Ясно",
            }
            for i in range(days)
        ]

    monkeypatch.setattr(server.weather_api, "geocode", fake_geocode)
    monkeypatch.setattr(server.weather_api, "daily_forecast", fake_forecast)
    result = server.get_forecast("Москва", 99)
    assert captured["days"] == 3
    assert len(result["days"]) == 3


def test_invalid_city_raises_value_error(monkeypatch):
    def fake_geocode(city):
        raise weather_api.WeatherError("Город не найден: Xyz")

    monkeypatch.setattr(server.weather_api, "geocode", fake_geocode)
    with pytest.raises(ValueError):
        server.get_weather("Xyz")


def test_stdio_lists_two_tools():
    tools = asyncio.run(list_tools())
    assert sorted(tool.name for tool in tools) == ["get_forecast", "get_weather"]


def test_get_weather_schema():
    tools = asyncio.run(list_tools())
    tool = next(t for t in tools if t.name == "get_weather")
    assert tool.description
    assert tool.input_schema["required"] == ["city"]
    assert tool.input_schema["properties"]["city"]["type"] == "string"


def test_get_forecast_schema_default_days():
    tools = asyncio.run(list_tools())
    tool = next(t for t in tools if t.name == "get_forecast")
    schema = tool.input_schema
    assert schema["required"] == ["city"]
    assert schema["properties"]["days"]["default"] == 3
