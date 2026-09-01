

# from langchain_core.tools import tool

# from app.models.schemas import DataSource, NormalizedResult
# from app.tools.common import seeded_random
# from app.tools.geoapify_client import geocode_place, places_search

# DEFAULT_ATTRACTION_CATEGORIES = "tourism.attraction,tourism.sights,entertainment,leisure.park"
# _LIKELY_FREE_CATEGORY_KEYWORDS = ("park", "square", "plaza", "viewpoint", "beach", "monument", "memorial", "natural")


# def _category_label(categories: list[str]) -> str:
#     for c in categories:
#         if c.startswith(("tourism.", "entertainment.", "leisure.", "beach.", "natural.")):
#             return c.split(".")[-1].replace("_", " ").title()
#     return "Attraction"


# def _build_categories_query(preferences: list[str] | None) -> str:
#     """Dynamically append category targets (e.g. beach, natural) based on user preferences."""
#     categories = DEFAULT_ATTRACTION_CATEGORIES
#     if not preferences:
#         return categories

#     pref_str = " ".join(preferences).lower()
#     if "beach" in pref_str and "beach" not in categories:
#         categories += ",beach,natural.beach"
#     if "park" in pref_str or "nature" in pref_str:
#         categories += ",leisure.park,national_park"
#     return categories


# async def _search_live(destination: str, preferences: list[str] | None) -> list[NormalizedResult]:
#     coords = await geocode_place(destination)
#     if not coords:
#         return []
#     lon, lat = coords
    
#     categories_query = _build_categories_query(preferences)
#     features = await places_search(categories_query, lon, lat, radius_m=15000, limit=15)

#     results = []
#     pref_terms = [p.lower().strip() for p in (preferences or []) if p.strip()]

#     for feature in features:
#         props = feature.get("properties", {})
#         name = props.get("name") or props.get("address_line1")
#         if not name:
#             continue
#         place_id = props.get("place_id", name)
#         rng = seeded_random("attraction-price", place_id)
#         categories = props.get("categories", [])
#         category = _category_label(categories)
        
#         # Check against both category string AND place name for preference matches
#         category_and_name = f"{category} {name}".lower()
#         matches = bool(pref_terms and any(term in category_and_name for term in pref_terms))

#         likely_free = any(kw in category_and_name for kw in _LIKELY_FREE_CATEGORY_KEYWORDS)
#         estimated_cost = 0.0 if likely_free else float(rng.randint(500, 6000))

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
#         # Sort so items matching preferences appear at the top of the list
#         results.sort(key=lambda r: not r.details.get("matches_preferences", False))

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
no credit card; OpenStreetMap-backed), with an LLM-generated rough
suggestion as a last resort when Geoapify has no venues for the area.

Important honesty note: the LLM fallback does NOT invent specific
attraction names or addresses — only a generic category-type suggestion
with an estimated cost. A fabricated attraction name would read as a
real place someone could show up to, which is a materially worse kind
of dishonesty than an estimated price. It's always labeled
source=ESTIMATED (never LIVE), with llm_generated=True in details.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.config import get_settings
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
    """Dynamically append category targets (e.g. beach, natural) based
    on user preferences. Every token here must be a real Geoapify
    category (dotted path) — a bare, unnamespaced token like "beach"
    is not valid and can cause Geoapify to reject the whole request,
    which was previously causing attraction search to silently return
    nothing whenever "beach" was in preferences."""
    categories = DEFAULT_ATTRACTION_CATEGORIES
    if not preferences:
        return categories

    pref_str = " ".join(preferences).lower()
    if "beach" in pref_str and "natural.beach" not in categories:
        categories += ",natural.beach"
    if "park" in pref_str or "nature" in pref_str:
        categories += ",leisure.park,national_park"
    return categories


async def _search_geoapify(destination: str, preferences: list[str] | None) -> list[NormalizedResult]:
    """Real venues from Geoapify. Returns [] if nothing was found near
    this destination — never an error, never fabricated data."""
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


class _LLMAttractionSuggestion(BaseModel):
    category: str = Field(description="Attraction type, e.g. 'Historic old town', 'Beach/waterfront', 'Museum'")
    estimated_price_inr: float = Field(description="Rough entry/activity cost estimate in INR, 0 if typically free")
    note: str = Field(description="One short sentence on why this type of attraction suits the destination")


class _LLMAttractionSuggestions(BaseModel):
    suggestions: list[_LLMAttractionSuggestion] = Field(default_factory=list)


async def _llm_suggest(destination: str, preferences: list[str] | None,
                        categories: str) -> list[NormalizedResult]:
    """Last-resort suggestions when Geoapify found nothing near this
    destination. Deliberately generic — no invented attraction names or
    addresses, just plausible category-type + cost suggestions, clearly
    labeled as the model's rough guess with no live data behind it. Any
    failure (rate limit, malformed output, etc.) returns an empty list
    rather than crashing the trip plan, same as every other tool."""
    settings = get_settings()
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.3,
        max_tokens=400,
    ).with_structured_output(_LLMAttractionSuggestions)

    messages = [
        SystemMessage(content=(
            "You suggest 3 generic attraction TYPES (not specific named venues — you have no real "
            "listings to draw from) that would plausibly be available at a given destination, with a "
            "rough entry/activity cost estimate in INR (0 if that type is typically free, like a park "
            "or public beach). Weight suggestions toward the traveler's stated preferences if given. "
            "Do NOT invent attraction names, addresses, or claim any specific place exists. Return "
            "ONLY the structured suggestions, no commentary."
        )),
        HumanMessage(content=(
            f"Destination: {destination}. Traveler preferences: {', '.join(preferences) if preferences else 'none stated'}. "
            f"Venue categories being searched: {categories}."
        )),
    ]

    try:
        result: _LLMAttractionSuggestions = await llm.ainvoke(messages)
    except Exception:  # noqa: BLE001 - best-effort fallback; any failure here just means no
                        # attraction data for this destination, never a crash.
        return []

    pref_terms = [p.lower().strip() for p in (preferences or []) if p.strip()]
    results = []
    for s in result.suggestions:
        if s.estimated_price_inr < 0:
            continue
        category_lower = s.category.lower()
        results.append(NormalizedResult(
            kind="attraction",
            name=f"Suggested: {s.category} (type only, not a specific venue)",
            location=destination,
            rating=None,
            price=round(s.estimated_price_inr, 2),
            currency="INR",
            source=DataSource.ESTIMATED,
            details={
                "category": s.category,
                "matches_preferences": bool(pref_terms and any(t in category_lower for t in pref_terms)),
                "price_estimated": True,
                "llm_generated": True,
                "note": f"No real venues found near this destination via Geoapify. This is a generic "
                        f"category suggestion, not a specific real attraction: {s.note}",
            },
        ))
    return results


@tool
async def attraction_search(destination: str, preferences: list[str] | None = None) -> list[dict]:
    """Find real attractions/activities in destination via Geoapify
    (OpenStreetMap data), optionally weighted toward preferences (e.g.
    'adventure', 'culture'). Venue name/address are live; cost is a
    category-based estimate since ticket prices aren't available from
    any free API. If Geoapify finds nothing near this destination,
    falls back to a generic LLM-suggested attraction type and cost
    (clearly labeled source=estimated, no invented venue names) rather
    than returning nothing."""
    categories_query = _build_categories_query(preferences)
    results = await _search_geoapify(destination, preferences)
    if not results:
        results = await _llm_suggest(destination, preferences, categories_query)
    return [r.model_dump(mode="json") for r in results]