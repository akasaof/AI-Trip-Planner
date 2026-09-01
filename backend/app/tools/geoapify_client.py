
import httpx

from app.config import get_settings
from app.tools.common import cache_get, cache_set

GEOAPIFY_BASE = "https://api.geoapify.com"


async def geocode_place(place: str) -> tuple[float, float] | None:
    """Resolve a free-text place name (e.g. 'Dubai') to (lon, lat) via
    Geoapify Geocoding. Cached for 24h since these don't change."""
    settings = get_settings()
    if not settings.geoapify_api_key or not place:
        return None

    cache_key = f"geoapify_geocode:{place.lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            resp = await client.get(
                f"{GEOAPIFY_BASE}/v1/geocode/search",
                params={"text": place, "apiKey": settings.geoapify_api_key, "limit": 1},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return None

    features = data.get("features", [])
    if not features:
        return None
    lon, lat = features[0]["geometry"]["coordinates"]
    cache_set(cache_key, (lon, lat), ttl_seconds=60 * 60 * 24)
    return (lon, lat)


async def places_search(categories: str, lon: float, lat: float, radius_m: int = 8000, limit: int = 10) -> list[dict]:
    """Raw Geoapify Places API v2 search within a radius. Returns the
    list of GeoJSON features, or an empty list on any failure/missing
    key — never raises."""
    settings = get_settings()
    if not settings.geoapify_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            resp = await client.get(
                f"{GEOAPIFY_BASE}/v2/places",
                params={
                    "categories": categories,
                    "filter": f"circle:{lon},{lat},{radius_m}",
                    "bias": f"proximity:{lon},{lat}",
                    "limit": limit,
                    "apiKey": settings.geoapify_api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return []
    return data.get("features", [])
