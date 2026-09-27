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
