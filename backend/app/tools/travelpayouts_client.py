
import httpx

from app.config import get_settings
from app.tools.common import cache_get, cache_set

AUTOCOMPLETE_BASE = "https://autocomplete.travelpayouts.com"


async def resolve_iata(keyword: str) -> str | None:
    """Resolve a free-text place name (e.g. 'Chennai') to an IATA
    city/airport code via Travelpayouts' public autocomplete endpoint.
    No token required for this one. Cached for 24h."""

    if not keyword:
        print("Keyword error")
        return None

    cache_key = f"tp_iata:{keyword.lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            resp = await client.get(
                f"{AUTOCOMPLETE_BASE}/places2",
                params={"term": keyword, "locale": "en", "types[]": ["city", "airport"]},
            )
            resp.raise_for_status()
            data = resp.json()
            print("data",data)
    except httpx.HTTPError:
        print("Exexption error")
        return None
    

    if not isinstance(data, list) or not data:
        print("Instance error")
        return None
    code = data[0].get("code")
    if code:
        cache_set(cache_key, code, ttl_seconds=60 * 60 * 24)
    return code

