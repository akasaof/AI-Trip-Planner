
# import httpx
# from langchain_core.tools import tool

# from app.config import get_settings
# from app.models.schemas import DataSource, NormalizedResult
# from app.tools.travelpayouts_client import resolve_iata

# # PRICES_BASE = "https://api.travelpayouts.com/v1/prices/cheap"

# PRICES_BASE = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


# async def _search_live(origin: str, destination: str, start_date: str, travelers: int) -> list[NormalizedResult]:
#     settings = get_settings()
#     if not settings.travelpayouts_token:
#         print("No token")
#         return []

#     origin_code = await resolve_iata(origin)
#     dest_code = await resolve_iata(destination)
#     print(origin_code)
#     print(dest_code)
#     if not origin_code or not dest_code:
#         print("IATA error")
#         return []

#     try:
#         async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
#             resp = await client.get(
#                 PRICES_BASE,
#                 params={
#                     "origin": origin_code,
#                     "destination": dest_code,
#                     "currency": "inr",
#                     "token": settings.travelpayouts_token,
#                 },
#             )
#             # print("STATUS:", resp.status_code)
#             # print("URL:", resp.url)
#             resp.raise_for_status()
#             data = resp.json()
#             # print(data)
#     except httpx.HTTPError:
#         print("Exception")
#         return []

#     if not data.get("success"):
#         print("Data error")
#         return []

#     route_data = data.get("data", {}).get(dest_code, {})
#     results = []
#     for entry in route_data.values():
#         try:
#             price = float(entry["price"])
#             results.append(NormalizedResult(
#                 kind="flight",
#                 name=f"{entry.get('airline', '?')} {origin_code}-{dest_code}",
#                 location=f"{origin} -> {destination}",
#                 price=price,
#                 currency="INR",
#                 source=DataSource.LIVE,
#                 details={
#                     "airline": entry.get("airline"),
#                     "stops": entry.get("transfers", 0),
#                     "duration_minutes": entry.get("duration"),
#                     "departure_date": entry.get("departure_at", start_date),
#                     "travelers": travelers,
#                     "cached_recent_fare": True,
#                     "note": "Recently observed fare for this route (Travelpayouts cache), not a live "
#                             "quote for your exact date.",
#                 },
#             ))
#         except (KeyError, TypeError, ValueError):
#             continue
#     return sorted(results, key=lambda r: r.price or 0)






# @tool
# async def flight_search(origin: str, destination: str, start_date: str, travelers: int = 2) -> list[dict]:
#     """Search recently-observed cached flight fares from origin to
#     destination via Travelpayouts/Aviasales (free tier). Prices are
#     per-person and reflect recent market data for the route, not a live
#     quote for your exact date — no free API provides that. Returns an
#     empty list if TRAVELPAYOUTS_TOKEN isn't configured or no cached
#     fares exist for this route."""
#     print(origin, destination, start_date, travelers)

#     results = await _search_live(origin=origin, destination=destination, start_date=start_date, travelers=travelers)
#     print("flights", results)
#     return [r.model_dump(mode="json") for r in results]




import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models.schemas import DataSource, NormalizedResult
from app.tools.travelpayouts_client import resolve_iata

PRICES_BASE = "https://api.travelpayouts.com/v1/prices/cheap"


async def _search_cache(origin: str, origin_code: str, destination: str, dest_code: str,
                         start_date: str, travelers: int) -> list[NormalizedResult]:
    """Real cached fares from Travelpayouts. Returns [] if there's
    nothing cached for this exact route — never an error, never
    fabricated data."""
    settings = get_settings()
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
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return []

    if not data.get("success"):
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


class _LLMFareEstimate(BaseModel):
    price_per_person_inr: float = Field(description="Rough one-way economy fare estimate, in INR, per person")
    reasoning: str = Field(description="One short sentence explaining the estimate (route length/region)")


async def _llm_estimate(origin: str, origin_code: str, destination: str, dest_code: str,
                         travelers: int) -> list[NormalizedResult]:
    settings = get_settings()
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.2,
        max_tokens=200,
    ).with_structured_output(_LLMFareEstimate)

    messages = [
        SystemMessage(content=(
            "You estimate a rough one-way economy flight fare in INR, per person, given only an "
            "origin and destination airport/city code. You have no live data — base this purely on "
            "typical fare patterns for routes of similar distance and region (e.g. domestic "
            "short-haul, regional international, long-haul). Be realistic and conservative. Return "
            "ONLY the structured estimate, no commentary."
        )),
        HumanMessage(content=f"Origin: {origin} ({origin_code}). Destination: {destination} ({dest_code})."),
    ]

    try:
        result: _LLMFareEstimate = await llm.ainvoke(messages)
    except Exception:  # noqa: BLE001 - best-effort fallback; any failure here (rate limit,
                        # malformed structured output, etc.) just means no flight data for this
                        # route, never a crash.
        return []

    if result.price_per_person_inr <= 0:
        return []

    return [NormalizedResult(
        kind="flight",
        name=f"Estimated fare ({origin_code}-{dest_code})",
        location=f"{origin} -> {destination}",
        price=round(result.price_per_person_inr, 2),
        currency="INR",
        source=DataSource.ESTIMATED,
        details={
            "travelers": travelers,
            "price_estimated": True,
            "llm_generated": True,
            "note": f"No cached fares found for this route via Travelpayouts. This is the model's "
                    f"rough estimate, not a real quote from any airline or booking system: "
                    f"{result.reasoning}",
        },
    )]


@tool
async def flight_search(origin: str, destination: str, start_date: str, travelers: int = 2) -> list[dict]:
    """Search recently-observed cached flight fares from origin to
    destination via Travelpayouts/Aviasales (free tier). Prices are
    per-person and reflect recent market data for the route, not a live
    quote for your exact date. If no cached fares exist for this route,
    falls back to a rough LLM-generated estimate (clearly labeled
    source=estimated, never live) rather than returning nothing.
    Returns an empty list only if TRAVELPAYOUTS_TOKEN isn't configured
    or the origin/destination can't be resolved to airport codes at
    all."""
    settings = get_settings()
    if not settings.travelpayouts_token:
        return []

    origin_code = await resolve_iata(origin)
    dest_code = await resolve_iata(destination)
    if not origin_code or not dest_code:
        return []

    results = await _search_cache(origin, origin_code, destination, dest_code, start_date, travelers)
    if not results:
        results = await _llm_estimate(origin, origin_code, destination, dest_code, travelers)
    return [r.model_dump(mode="json") for r in results]