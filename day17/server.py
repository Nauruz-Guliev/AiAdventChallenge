from mcp.server import MCPServer

import weather_api

mcp = MCPServer("weather")

MIN_FORECAST_DAYS = 1
MAX_FORECAST_DAYS = 7


@mcp.tool()
def get_weather(city: str) -> dict:
    """Текущая погода в городе.

    Args:
        city: Название города, например "Москва" или "Almaty".
    """
    try:
        place = weather_api.geocode(city)
        current = weather_api.current_weather(place.latitude, place.longitude)
    except weather_api.WeatherError as exc:
        raise ValueError(str(exc)) from exc
    return {
        "city": place.name,
        "latitude": place.latitude,
        "longitude": place.longitude,
        **current,
    }


@mcp.tool()
def get_forecast(city: str, days: int = 3) -> dict:
    """Прогноз погоды на несколько дней.

    Args:
        city: Название города, например "Москва".
        days: Число дней прогноза от 1 до 7. По умолчанию 3.
    """
    days = max(MIN_FORECAST_DAYS, min(MAX_FORECAST_DAYS, days))
    try:
        place = weather_api.geocode(city)
        forecast = weather_api.daily_forecast(place.latitude, place.longitude, days)
    except weather_api.WeatherError as exc:
        raise ValueError(str(exc)) from exc
    return {"city": place.name, "days": forecast}


if __name__ == "__main__":
    mcp.run()
