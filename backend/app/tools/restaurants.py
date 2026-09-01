
from langchain_core.tools import tool

from app.models.schemas import DataSource, NormalizedResult
from app.tools.common import seeded_random
from app.tools.geoapify_client import geocode_place, places_search

RESTAURANT_CATEGORIES = "catering.restaurant,catering.fast_food,catering.cafe"
_BUDGET_LEVEL_ESTIMATE = {"low": 400, "mid": 900, "high": 2200}


def _cuisine_from_categories(categories: list[str]) -> str:
    for c in categories:
        if c.startswith("catering."):
            return c.split(".")[-1].replace("_", " ").title()
    return "Restaurant"


async def _search_live(location: str, cuisine_preference: str | None, budget_level: str) -> list[NormalizedResult]:
    coords = await geocode_place(location)
    if not coords:
        return []
    lon, lat = coords
    features = await places_search(RESTAURANT_CATEGORIES, lon, lat, radius_m=8000, limit=8)

    base_estimate = _BUDGET_LEVEL_ESTIMATE.get(budget_level, 900)
    results = []
    for feature in features:
        props = feature.get("properties", {})
        name = props.get("name") or props.get("address_line1")
        if not name:
            continue
        place_id = props.get("place_id", name)
        rng = seeded_random("restaurant-price", place_id)
        categories = props.get("categories", [])
        cuisine = _cuisine_from_categories(categories)
        estimated_cost = base_estimate + rng.randint(-100, 300)
        results.append(NormalizedResult(
            kind="restaurant",
            name=name,
            location=props.get("formatted", location),
            rating=None,  # Geoapify/OSM data doesn't include venue ratings
            price=round(estimated_cost, 2),
            currency="INR",
            source=DataSource.LIVE,
            details={
                "cuisine": cuisine_preference or cuisine,
                "meal": "per person, estimated",
                "price_estimated": True,
                "place_id": place_id,
            },
        ))
    return results


@tool
async def restaurant_search(location: str, cuisine_preference: str | None = None, budget_level: str = "mid") -> list[dict]:
    """Find real restaurants near a location via Geoapify (OpenStreetMap
    data), optionally noting a cuisine preference and budget_level
    ('low'|'mid'|'high'). Venue name/address are live; per-meal cost is
    a category-based estimate since no free API exposes real menu
    prices. Returns an empty list if GEOAPIFY_API_KEY isn't configured
    or the destination can't be geocoded."""
    results = await _search_live(location, cuisine_preference, budget_level)
    return [r.model_dump(mode="json") for r in results]
