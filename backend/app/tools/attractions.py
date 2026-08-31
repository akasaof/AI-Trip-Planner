# """
# Attraction search tool — live venue data via Geoapify Places API (free,
# no credit card; OpenStreetMap-backed). See geoapify_client.py for why
# this replaced Foursquare. Ticket/entry prices aren't available from any
# free public API, so `price` here is a category-based estimate (0 for
# categories that are typically free — parks, plazas, viewpoints),
# flagged via details.price_estimated. Rating is left null rather than
# invented, since OSM-based place data doesn't include it.
# """
# from langchain_core.tools import tool

# from app.models.schemas import DataSource, NormalizedResult
# from app.tools.common import seeded_random
# from app.tools.geoapify_client import geocode_place, places_search

# ATTRACTION_CATEGORIES = "tourism.attraction,tourism.sights,entertainment,leisure.park"
# _LIKELY_FREE_CATEGORY_KEYWORDS = ("park", "square", "plaza", "viewpoint", "beach", "monument", "memorial")


# def _category_label(categories: list[str]) -> str:
#     for c in categories:
#         if c.startswith(("tourism.", "entertainment.", "leisure.")):
#             return c.split(".")[-1].replace("_", " ").title()
#     return "Attraction"


# async def _search_live(destination: str, preferences: list[str] | None) -> list[NormalizedResult]:
#     coords = await geocode_place(destination)
#     if not coords:
#         return []
#     lon, lat = coords
#     features = await places_search(ATTRACTION_CATEGORIES, lon, lat, radius_m=10000, limit=12)

#     results = []
#     for feature in features:
#         props = feature.get("properties", {})
#         name = props.get("name") or props.get("address_line1")
#         if not name:
#             continue
#         place_id = props.get("place_id", name)
#         rng = seeded_random("attraction-price", place_id)
#         categories = props.get("categories", [])
#         category = _category_label(categories)
#         likely_free = any(kw in category.lower() for kw in _LIKELY_FREE_CATEGORY_KEYWORDS)
#         estimated_cost = 0.0 if likely_free else float(rng.randint(500, 6000))
#         matches = bool(preferences and any(p.lower() in category.lower() for p in preferences))
#         results.append(NormalizedResult(
#             kind="attraction",
#             name=name,
#             location=props.get("formatted", destination),
#             rating=None,  # Geoapify/OSM data doesn't include venue ratings
#             price=estimated_cost,
#             currency="INR",
#             source=DataSource.LIVE,
#             details={
#                 "category": category,
#                 "matches_preferences": matches,
#                 "price_estimated": True,
#                 "place_id": place_id,
#             },
#         ))
#     if preferences:
#         results.sort(key=lambda r: not r.details.get("matches_preferences"))
#     return results


# @tool
# async def attraction_search(destination: str, preferences: list[str] | None = None) -> list[dict]:
#     """Find real attractions/activities in destination via Geoapify
#     (OpenStreetMap data), optionally weighted toward preferences (e.g.
#     'adventure', 'culture'). Venue name/address are live; cost is a
#     category-based estimate since ticket prices aren't available from
#     any free API. Returns an empty list if GEOAPIFY_API_KEY isn't
#     configured or the destination can't be geocoded."""
#     results = await _search_live(destination, preferences)
#     return [r.model_dump(mode="json") for r in results]



"""
Attraction search tool — live venue data via Geoapify Places API (free,
no credit card; OpenStreetMap-backed). See geoapify_client.py for why
this replaced Foursquare. Ticket/entry prices aren't available from any
free public API, so `price` here is a category-based estimate (0 for
categories that are typically free — parks, plazas, viewpoints),
flagged via details.price_estimated. Rating is left null rather than
invented, since OSM-based place data doesn't include it.
"""
from langchain_core.tools import tool

from app.models.schemas import DataSource, NormalizedResult
from app.tools.common import seeded_random
from app.tools.geoapify_client import geocode_place, places_search

DEFAULT_ATTRACTION_CATEGORIES = "tourism.attraction,tourism.sights,entertainment,leisure.park"
_LIKELY_FREE_CATEGORY_KEYWORDS = ("park", "square", "plaza", "viewpoint", "beach", "monument", "memorial", "natural")


def _category_label(categories: list[str]) -> str:
    for c in categories:
        if c.startswith(("tourism.", "entertainment.", "leisure.", "beach.", "natural.")):
            return c.split(".")[-1].replace("_", " ").title()
    return "Attraction"


def _build_categories_query(preferences: list[str] | None) -> str:
    """Dynamically append category targets (e.g. beach, natural) based on user preferences."""
    categories = DEFAULT_ATTRACTION_CATEGORIES
    if not preferences:
        return categories

    pref_str = " ".join(preferences).lower()
    if "beach" in pref_str and "beach" not in categories:
        categories += ",beach,natural.beach"
    if "park" in pref_str or "nature" in pref_str:
        categories += ",leisure.park,national_park"
    return categories


async def _search_live(destination: str, preferences: list[str] | None) -> list[NormalizedResult]:
    coords = await geocode_place(destination)
    if not coords:
        return []
    lon, lat = coords
    
    categories_query = _build_categories_query(preferences)
    features = await places_search(categories_query, lon, lat, radius_m=15000, limit=15)

    results = []
    pref_terms = [p.lower().strip() for p in (preferences or []) if p.strip()]

    for feature in features:
        props = feature.get("properties", {})
        name = props.get("name") or props.get("address_line1")
        if not name:
            continue
        place_id = props.get("place_id", name)
        rng = seeded_random("attraction-price", place_id)
        categories = props.get("categories", [])
        category = _category_label(categories)
        
        # Check against both category string AND place name for preference matches
        category_and_name = f"{category} {name}".lower()
        matches = bool(pref_terms and any(term in category_and_name for term in pref_terms))

        likely_free = any(kw in category_and_name for kw in _LIKELY_FREE_CATEGORY_KEYWORDS)
        estimated_cost = 0.0 if likely_free else float(rng.randint(500, 6000))

        results.append(NormalizedResult(
            kind="attraction",
            name=name,
            location=props.get("formatted", destination),
            rating=None,  # Geoapify/OSM data doesn't include venue ratings
            price=estimated_cost,
            currency="INR",
            source=DataSource.LIVE,
            details={
                "category": category,
                "matches_preferences": matches,
                "price_estimated": True,
                "place_id": place_id,
            },
        ))

    if preferences:
        # Sort so items matching preferences appear at the top of the list
        results.sort(key=lambda r: not r.details.get("matches_preferences", False))

    return results


@tool
async def attraction_search(destination: str, preferences: list[str] | None = None) -> list[dict]:
    """Find real attractions/activities in destination via Geoapify
    (OpenStreetMap data), optionally weighted toward preferences (e.g.
    'adventure', 'culture'). Venue name/address are live; cost is a
    category-based estimate since ticket prices aren't available from
    any free API. Returns an empty list if GEOAPIFY_API_KEY isn't
    configured or the destination can't be geocoded."""
    results = await _search_live(destination, preferences)
    return [r.model_dump(mode="json") for r in results]