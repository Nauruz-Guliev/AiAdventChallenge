import pytest

import weather_api
from weather_api import WeatherError, describe_weather


def test_describe_weather_known_codes():
    assert describe_weather(0) == "Ясно"
    assert describe_weather(3) == "Пасмурно"
    assert describe_weather(95) == "Гроза"


def test_describe_weather_unknown_code():
    assert "123" in describe_weather(123)


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
            "current": {
                "temperature_2m": -3.2,
                "apparent_temperature": -7.0,
                "relative_humidity_2m": 85,
                "wind_speed_10m": 12.4,
                "weather_code": 3,
            }
        },
    )
    result = weather_api.current_weather(55.75, 37.62)
    assert result == {
        "temperature_c": -3.2,
        "feels_like_c": -7.0,
        "humidity_percent": 85,
        "wind_kmh": 12.4,
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
            "daily": {
                "time": ["2026-09-27", "2026-09-28"],
                "temperature_2m_max": [4.1, 5.0],
                "temperature_2m_min": [-1.0, 0.0],
                "precipitation_probability_max": [20, 10],
                "weather_code": [2, 0],
            }
        },
    )
    result = weather_api.daily_forecast(55.75, 37.62, 2)
    assert len(result) == 2
    assert result[0] == {
        "date": "2026-09-27",
        "temp_max_c": 4.1,
        "temp_min_c": -1.0,
        "precipitation_probability": 20,
        "weather": "Переменная облачность",
    }


def test_daily_forecast_missing_data(monkeypatch):
    monkeypatch.setattr(weather_api, "_get_json", lambda url, params: {"daily": {}})
    with pytest.raises(WeatherError):
        weather_api.daily_forecast(55.75, 37.62, 3)
