
import httpx
from langchain_core.tools import tool

from app.config import get_settings
from app.models.schemas import DataSource, NormalizedResult


async def _fetch_live(destination: str) -> NormalizedResult | None:
    settings = get_settings()
    if not settings.openweather_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": destination, "appid": settings.openweather_api_key, "units": "metric"},
            )
            resp.raise_for_status()
            data = resp.json()
        return NormalizedResult(
            kind="weather",
            name=f"Current conditions in {destination}",
            location=destination,
            source=DataSource.LIVE,
            details={
                "temp_c_high": data["main"].get("temp_max", data["main"].get("temp")),
                "temp_c_low": data["main"].get("temp_min", data["main"].get("temp")),
                "condition": data["weather"][0]["description"],
                "humidity": data["main"].get("humidity"),
                "is_current_conditions_not_future_forecast": True,
            },
        )
    except (httpx.HTTPError, KeyError, IndexError):
        return None


@tool
async def weather_lookup(destination: str, date_str: str) -> dict:
    """Get live current weather conditions for destination via
    OpenWeatherMap. Free-tier weather APIs can't forecast a specific
    date far in the future, so this returns today's real conditions as a
    seasonal proxy for trip dates beyond the short-range forecast window
    — never an invented forecast. Returns an empty dict if
    OPENWEATHER_API_KEY isn't configured."""
    result = await _fetch_live(destination)
    return result.model_dump(mode="json") if result else {}
