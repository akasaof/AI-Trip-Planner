
import httpx
from langchain_core.tools import tool

from app.config import get_settings
from app.models.schemas import DataSource, NormalizedResult

ORS_BASE = "https://api.openrouteservice.org"


async def _fetch_google(origin: str, destination: str) -> NormalizedResult | None:
    settings = get_settings()
    if not settings.google_maps_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/distancematrix/json",
                params={"origins": origin, "destinations": destination, "key": settings.google_maps_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        element = data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            return None
        return NormalizedResult(
            kind="distance",
            name=f"{origin} -> {destination}",
            source=DataSource.LIVE,
            details={
                "distance_km": round(element["distance"]["value"] / 1000, 1),
                "duration_minutes": round(element["duration"]["value"] / 60),
            },
        )
    except (httpx.HTTPError, KeyError, IndexError):
        return None


async def _geocode_ors(client: httpx.AsyncClient, api_key: str, place: str) -> tuple[float, float] | None:
    resp = await client.get(
        f"{ORS_BASE}/geocode/search",
        params={"api_key": api_key, "text": place, "size": 1},
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        return None
    lon, lat = features[0]["geometry"]["coordinates"]
    return lon, lat


async def _fetch_ors(origin: str, destination: str) -> NormalizedResult | None:
    settings = get_settings()
    if not settings.openrouteservice_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            origin_coords = await _geocode_ors(client, settings.openrouteservice_api_key, origin)
            dest_coords = await _geocode_ors(client, settings.openrouteservice_api_key, destination)
            if not origin_coords or not dest_coords:
                return None
            resp = await client.get(
                f"{ORS_BASE}/v2/directions/driving-car",
                params={
                    "api_key": settings.openrouteservice_api_key,
                    "start": f"{origin_coords[0]},{origin_coords[1]}",
                    "end": f"{dest_coords[0]},{dest_coords[1]}",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        summary = data["features"][0]["properties"]["summary"]
        return NormalizedResult(
            kind="distance",
            name=f"{origin} -> {destination}",
            source=DataSource.LIVE,
            details={
                "distance_km": round(summary["distance"] / 1000, 1),
                "duration_minutes": round(summary["duration"] / 60),
            },
        )
    except (httpx.HTTPError, KeyError, IndexError):
        return None


@tool
async def map_distance(origin: str, destination: str) -> dict:
    """Get live driving distance and estimated travel time between two
    named places, via Google Maps (if GOOGLE_MAPS_API_KEY is set) or
    OpenRouteService (if OPENROUTESERVICE_API_KEY is set). Returns an
    empty dict if neither is configured or the lookup fails."""
    result = await _fetch_google(origin, destination) or await _fetch_ors(origin, destination)
    return result.model_dump(mode="json") if result else {}
