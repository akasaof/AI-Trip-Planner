from app.tools import ALL_TOOLS
from app.models.schemas import (NormalizedResult,ToolCallRecord,TripRequirement)

from app.db import messages_collection, tool_results_collection, trips_collection

TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
REQUIRED_TOOLS = ["flight_search", "hotel_search", "restaurant_search", "attraction_search", "weather_lookup"]






def _tool_args_for_requirement(requirement: TripRequirement) -> dict[str, dict]:
    nights = max((requirement.duration_days or 1) - 1, 1)
    start_date_str = str(requirement.start_date) if requirement.start_date else ""
    return {
        "flight_search": {
            "origin": requirement.departure_city or "Chennai",
            "destination": requirement.destination or "",
            "start_date": start_date_str,
            "travelers": requirement.travelers or 1,
        },
        "hotel_search": {
            "destination": requirement.destination or "",
            "start_date": start_date_str,
            "nights": nights,
            "travelers": requirement.travelers or 1,
        },
        "restaurant_search": {
            "location": requirement.destination or "",
            "cuisine_preference": None,
            "budget_level": "mid",
        },
        "attraction_search": {
            "destination": requirement.destination or "",
            "preferences": requirement.preferences,
        },
        "weather_lookup": {
            "destination": requirement.destination or "",
            "date_str": start_date_str,
        },
    }



async def gather_tool_data(requirement: TripRequirement, trip_id: str) -> dict[str, list[NormalizedResult]]:
    """Deterministically calls the tools every complete trip plan needs
    (see the module docstring for why this isn't LLM-driven). Every call
    is still logged to tool_results for auditability, and a failure in
    one tool never blocks the others."""
    normalized: dict[str, list[NormalizedResult]] = {
        "flight": [], "hotel": [], "restaurant": [], "attraction": [], "weather": [], "distance": [],
    }
    args_by_tool = _tool_args_for_requirement(requirement)

    for tool_name in REQUIRED_TOOLS:
        tool_fn = TOOLS_BY_NAME[tool_name]
        args = args_by_tool[tool_name]
        record = ToolCallRecord(trip_id=trip_id, tool_name=tool_name, arguments=args)
        try:
            raw_result = await tool_fn.ainvoke(args)
            items = raw_result if isinstance(raw_result, list) else [raw_result]
            parsed = [NormalizedResult(**item) for item in items if isinstance(item, dict) and "kind" in item]
            record.results = parsed
            for p in parsed:
                normalized.setdefault(p.kind, []).append(p)
        except Exception as exc:  # noqa: BLE001 - one tool failing must never block the others
            record.error = str(exc)
        await tool_results_collection().insert_one(record.model_dump(mode="json"))

    return normalized


