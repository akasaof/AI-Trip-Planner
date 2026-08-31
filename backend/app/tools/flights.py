"""
Flight search tool — live data via Travelpayouts' Aviasales price-cache
API (free, self-serve). See travelpayouts_client.py for why this
replaced Amadeus. Returns recently-observed cached fares for the route,
grouped by number of transfers — not a live search for your exact
travel date, which no free API provides. Every result is labeled
accordingly via details.cached_recent_fare so it's never mistaken for a
guaranteed live quote.
"""
import httpx
from langchain_core.tools import tool

from app.config import get_settings
from app.models.schemas import DataSource, NormalizedResult
from app.tools.travelpayouts_client import resolve_iata

PRICES_BASE = "https://api.travelpayouts.com/v1/prices/cheap"


async def _search_live(origin: str, destination: str, start_date: str, travelers: int) -> list[NormalizedResult]:
    settings = get_settings()
    if not settings.travelpayouts_token:
        print("No token")
        return []

    origin_code = await resolve_iata(origin)
    dest_code = await resolve_iata(destination)
    print(origin_code)
    print(dest_code)
    if not origin_code or not dest_code:
        print("IATA error")
        return []

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            resp = await client.get(
                PRICES_BASE,
                params={
                    "origin": origin_code,
                    "destination": dest_code,
                    "currency": "inr",
                    "token": settings.travelpayouts_token,
                },
            )
            # print("STATUS:", resp.status_code)
            # print("URL:", resp.url)
            resp.raise_for_status()
            data = resp.json()
            # print(data)
    except httpx.HTTPError:
        print("Exception")
        return []

    if not data.get("success"):
        print("Data error")
        return []

    route_data = data.get("data", {}).get(dest_code, {})
    results = []
    for entry in route_data.values():
        try:
            price = float(entry["price"])
            results.append(NormalizedResult(
                kind="flight",
                name=f"{entry.get('airline', '?')} {origin_code}-{dest_code}",
                location=f"{origin} -> {destination}",
                price=price,
                currency="INR",
                source=DataSource.LIVE,
                details={
                    "airline": entry.get("airline"),
                    "stops": entry.get("transfers", 0),
                    "duration_minutes": entry.get("duration"),
                    "departure_date": entry.get("departure_at", start_date),
                    "travelers": travelers,
                    "cached_recent_fare": True,
                    "note": "Recently observed fare for this route (Travelpayouts cache), not a live "
                            "quote for your exact date.",
                },
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(results, key=lambda r: r.price or 0)


@tool
async def flight_search(origin: str, destination: str, start_date: str, travelers: int = 2) -> list[dict]:
    """Search recently-observed cached flight fares from origin to
    destination via Travelpayouts/Aviasales (free tier). Prices are
    per-person and reflect recent market data for the route, not a live
    quote for your exact date — no free API provides that. Returns an
    empty list if TRAVELPAYOUTS_TOKEN isn't configured or no cached
    fares exist for this route."""
    print(origin,destination,start_date,travelers)

    results = await _search_live(origin=origin, destination=destination, start_date=start_date, travelers=travelers)
    # print(results)
    return [r.model_dump(mode="json") for r in results]



