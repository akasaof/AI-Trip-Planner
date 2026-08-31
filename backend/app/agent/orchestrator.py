"""
Orchestrates the full workflow from Section 3 of the spec:

 1. receive request               -> handled by the router, passed in here
 2. extract structured trip fields -> extraction.extract_requirement
 3. validate / ask for missing dates -> _check_missing()
 4. RAG destination context        -> rag_search tool, called directly (always-on)
 5. select & call tools            -> deterministic calls to the required tools (see note below)
 6. normalize results              -> tools already return NormalizedResult
 7. calculate budget               -> deterministic Python function, NEVER the LLM
 8. build itinerary                -> deterministic day-by-day assembly, LLM only adds summaries
 9. validate consistency           -> pydantic validation; enrichment failures degrade silently
10. persist                        -> Mongo (trips / messages / tool_results)
11. return React-ready JSON        -> TripPlanResponse

Design note on step 5: earlier versions of this POC let the LLM decide
which of flights/hotels/restaurants/attractions/weather to call via a
LangChain tool-calling loop. In practice, on Groq's free/on_demand tier
(8000 tokens/request), asking a single completion to emit five parallel
tool calls reliably hit the TPM cap or produced truncated/malformed JSON
— which is what caused the 413s and 500s seen in testing. Since these
five tools are *always* needed for any complete trip (they're not
optional/conditional), calling them directly removes an entire class of
failure with no loss of capability: the LLM's judgment is used instead
where it actually adds value — grouping/sequencing the itinerary and
writing day summaries — and those calls are now small and bounded
regardless of trip length, so they can't blow the token budget on longer
trips either. `map_distance` and `currency_convert` remain available
LangChain tools for future agentic use (e.g. an "optimize my route"
follow-up) but aren't required for the base plan.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.agent.extraction import extract_requirement
from app.agent.prompts import PLANNING_SYSTEM_PROMPT
from app.config import get_settings
from app.db import messages_collection, tool_results_collection, trips_collection
from app.models.schemas import (
    BudgetBreakdown,
    ItineraryDay,
    ItineraryItem,
    Message,
    NormalizedResult,
    ToolCallRecord,
    TripPlanResponse,
    TripRequirement,
    TripSummary,
)
from app.tools import ALL_TOOLS
from app.tools.rag_tool import rag_search
from app.utils.budget import calculate_budget

TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
REQUIRED_TOOLS = ["flight_search", "hotel_search", "restaurant_search", "attraction_search", "weather_lookup"]


class _ItineraryBuildOutput(BaseModel):
    itinerary: list[ItineraryDay] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class _DaySummary(BaseModel):
    day_number: int
    summary: str


class _EnrichmentOutput(BaseModel):
    summaries: list[_DaySummary] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


def _planning_llm(max_tokens: int | None = None) -> ChatGroq:
    settings = get_settings()
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        max_tokens=max_tokens or settings.llm_max_tokens,
    )


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


async def _gather_tool_data(requirement: TripRequirement, trip_id: str) -> dict[str, list[NormalizedResult]]:
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


def _check_missing(requirement: TripRequirement) -> str | None:
    missing = requirement.missing_required_fields()
    if not missing:
        return None
    friendly = {
        "destination": "which destination you'd like to visit",
        "duration_days": "how many days the trip should be",
        "travelers": "how many travelers",
        "budget": "your total budget (and currency, if not INR)",
        "start_date": "your trip start date",
    }
    asks = [friendly.get(m, m) for m in missing]
    return "Before I can build a real, priced itinerary I need a couple more details: " + "; ".join(asks) + "."


def _select_for_budget(normalized: dict[str, list[NormalizedResult]]):
    flights = sorted(normalized.get("flight", []), key=lambda r: r.price or 0)
    hotels = sorted(normalized.get("hotel", []), key=lambda r: r.price or 0)
    attractions = normalized.get("attraction", [])[:4]
    selected_flight = flights[0] if flights else None
    selected_hotel = hotels[0] if hotels else None
    return selected_flight, selected_hotel, attractions


def _round_robin(pool: list[NormalizedResult], index: int) -> NormalizedResult | None:
    if not pool:
        return None
    return pool[index % len(pool)]


def _build_itinerary_skeleton(
    requirement: TripRequirement,
    normalized: dict[str, list[NormalizedResult]],
    selected_flight: NormalizedResult | None,
    selected_hotel: NormalizedResult | None,
) -> list[ItineraryDay]:
    """Deterministically assembles a complete day-by-day itinerary from
    normalized tool results. This always succeeds — no LLM call is on the
    critical path for the itinerary to exist at all, only for the
    (optional) narrative day summaries layered on afterward. Costs shown
    per item are computed directly from tool prices, so they're
    traceable and self-consistent within the itinerary regardless of
    trip length."""
    duration_days = requirement.duration_days or 1
    travelers = requirement.travelers or 1
    nights = max(duration_days - 1, 1)
    start_date = requirement.start_date

    restaurants = normalized.get("restaurant", [])
    attractions = normalized.get("attraction", [])
    restaurant_idx = 0
    attraction_idx = 0

    days: list[ItineraryDay] = []
    for day_num in range(1, duration_days + 1):
        items: list[ItineraryItem] = []
        day_date = start_date + timedelta(days=day_num - 1) if start_date else None

        if day_num == 1 and selected_flight:
            items.append(ItineraryItem(
                time="Morning",
                title=selected_flight.name,
                category="transport",
                location=selected_flight.location,
                estimated_cost=round((selected_flight.price or 0) * travelers, 2),
                currency=selected_flight.currency,
                source=selected_flight.source,
                notes=f"{travelers} traveler(s)",
            ))

        if selected_hotel:
            if day_num <= nights:
                items.append(ItineraryItem(
                    time="Afternoon" if day_num == 1 else "Morning",
                    title=f"{selected_hotel.name} ({'Check-in' if day_num == 1 else 'Overnight stay'})",
                    category="hotel",
                    location=selected_hotel.location,
                    estimated_cost=round(selected_hotel.price or 0, 2),
                    currency=selected_hotel.currency,
                    source=selected_hotel.source,
                ))
            elif day_num == duration_days and duration_days > 1:
                items.append(ItineraryItem(
                    time="Morning",
                    title=f"{selected_hotel.name} (Check-out)",
                    category="hotel",
                    location=selected_hotel.location,
                    estimated_cost=0,
                    currency=selected_hotel.currency,
                    source=selected_hotel.source,
                ))

        lunch = _round_robin(restaurants, restaurant_idx)
        if lunch:
            restaurant_idx += 1
            items.append(ItineraryItem(
                time="13:00",
                title=f"Lunch at {lunch.name}",
                category="meal",
                location=lunch.location,
                estimated_cost=round((lunch.price or 0) * travelers, 2),
                currency=lunch.currency,
                source=lunch.source,
            ))

        attraction = _round_robin(attractions, attraction_idx)
        if attraction:
            attraction_idx += 1
            items.append(ItineraryItem(
                time="15:00",
                title=attraction.name,
                category="activity",
                location=attraction.location,
                estimated_cost=round(attraction.price or 0, 2),
                currency=attraction.currency,
                source=attraction.source,
            ))

        dinner = _round_robin(restaurants, restaurant_idx)
        if dinner:
            restaurant_idx += 1
            items.append(ItineraryItem(
                time="20:00",
                title=f"Dinner at {dinner.name}",
                category="meal",
                location=dinner.location,
                estimated_cost=round((dinner.price or 0) * travelers, 2),
                currency=dinner.currency,
                source=dinner.source,
            ))

        daily_cost = round(sum(i.estimated_cost for i in items), 2)
        item_titles = ", ".join(i.title for i in items) or "Free day"
        days.append(ItineraryDay(
            day_number=day_num,
            date=day_date,
            items=items,
            daily_cost=daily_cost,
            summary=f"Day {day_num}: {item_titles}",
        ))

    return days


async def _enrich_with_summaries(
    requirement: TripRequirement,
    skeleton: list[ItineraryDay],
) -> _ItineraryBuildOutput:
    """Best-effort LLM pass that replaces the generic per-day summary
    with a one-sentence, human-written version and adds a short list of
    planning assumptions. Output is small and bounded by duration_days
    regardless of how much tool data exists, so it can't blow the token
    budget the way generating the full nested itinerary schema did. If
    this fails for any reason, the deterministic skeleton (which already
    has a serviceable summary) is returned unchanged — the itinerary is
    never empty."""
    settings = get_settings()
    compact_days = [
        {
            "day_number": d.day_number,
            "items": [{"title": i.title, "category": i.category, "time": i.time} for i in d.items],
        }
        for d in skeleton
    ]
    messages = [
        SystemMessage(content=PLANNING_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Here is a {requirement.duration_days}-day itinerary for {requirement.destination} with items "
            "already assigned to each day. Write ONE short, natural sentence per day summarizing it (under 20 "
            "words), and up to 3 short overall assumptions. Do not change, add, or remove any items — only "
            "summarize what's given.\n\n" + json.dumps(compact_days, default=str)
        )),
    ]
    try:
        llm = _planning_llm(max_tokens=min(settings.llm_max_tokens, 1200)).with_structured_output(_EnrichmentOutput)
        result: _EnrichmentOutput = await llm.ainvoke(messages)
    except Exception:  # noqa: BLE001 - enrichment is purely cosmetic; any failure here is silently
                        # absorbed and the deterministic skeleton's generic summaries stand as-is.
        return _ItineraryBuildOutput(itinerary=skeleton, assumptions=[])

    summary_by_day = {s.day_number: s.summary for s in result.summaries}
    enriched = []
    for d in skeleton:
        if d.day_number in summary_by_day:
            d = d.model_copy(update={"summary": summary_by_day[d.day_number]})
        enriched.append(d)
    return _ItineraryBuildOutput(itinerary=enriched, assumptions=result.assumptions)


def _weather_for_days(requirement: TripRequirement, weather_results: list[NormalizedResult]) -> dict:
    """Map available weather results onto day numbers so the itinerary
    builder (and UI) can show per-day forecasts."""
    by_date = {}
    for w in weather_results:
        d = w.details.get("date")
        if d:
            by_date[d] = w.details
    return by_date


async def plan_trip(trip_id: str, requirement: TripRequirement) -> TripPlanResponse:
    """Runs steps 4-11 of the workflow. Assumes requirement is already
    validated as complete (step 3 happened in the caller)."""
    rag_context = rag_search.invoke({"query": f"{requirement.destination} transport culture weather best time"})

    normalized = await _gather_tool_data(requirement, trip_id)

    selected_flight, selected_hotel, selected_activities = _select_for_budget(normalized)
    budget = calculate_budget(
        travelers=requirement.travelers or 1,
        duration_days=requirement.duration_days or 1,
        total_budget=requirement.budget or 0,
        currency=requirement.currency or "INR",
        selected_flight=selected_flight,
        selected_hotel=selected_hotel,
        selected_activities=selected_activities,
        nights=max((requirement.duration_days or 1) - 1, 1),
    )

    skeleton = _build_itinerary_skeleton(requirement, normalized, selected_flight, selected_hotel)
    built = await _enrich_with_summaries(requirement, skeleton)

    end_date = None
    if requirement.start_date and requirement.duration_days:
        end_date = requirement.start_date + timedelta(days=requirement.duration_days - 1)

    sources = sorted({r.source.value for group in normalized.values() for r in group} | {"cached"})

    response = TripPlanResponse(
        trip_id=trip_id,
        trip_summary=TripSummary(
            destination=requirement.destination or "",
            country=requirement.country,
            duration_days=requirement.duration_days or 0,
            travelers=requirement.travelers or 0,
            start_date=requirement.start_date,
            end_date=end_date,
            trip_type=requirement.trip_type,
        ),
        flights=normalized.get("flight", []),
        hotels=normalized.get("hotel", []),
        restaurants=normalized.get("restaurant", []),
        attractions=normalized.get("attraction", []),
        weather=normalized.get("weather", []),
        budget=budget,
        itinerary=built.itinerary,
        assumptions=built.assumptions,
        sources=sources,
    )
    return response


async def handle_user_message(trip_id: str, user_message: str) -> TripPlanResponse:
    """Top-level entry point used by both POST /trips (first message) and
    POST /trips/{id}/chat (follow-ups)."""
    trip_doc = await trips_collection().find_one({"_id": trip_id})
    prior_requirement = TripRequirement(**trip_doc["requirement"]) if trip_doc else TripRequirement()

    requirement = await extract_requirement(user_message, prior=prior_requirement)

    await messages_collection().insert_one(
        Message(trip_id=trip_id, role="user", content=user_message).model_dump(mode="json")
    )

    clarification = _check_missing(requirement)
    now_iso = date.today().isoformat()

    if clarification:
        await trips_collection().update_one(
            {"_id": trip_id},
            {"$set": {"requirement": requirement.model_dump(mode="json"), "updated_at": now_iso}},
            upsert=True,
        )
        response = TripPlanResponse(
            trip_id=trip_id,
            trip_summary=TripSummary(
                destination=requirement.destination or "unknown",
                duration_days=requirement.duration_days or 0,
                travelers=requirement.travelers or 0,
            ),
            budget=BudgetBreakdown(currency=requirement.currency or "INR"),
            needs_clarification=clarification,
        )
        await messages_collection().insert_one(
            Message(trip_id=trip_id, role="assistant", content=clarification).model_dump(mode="json")
        )
        return response

    response = await plan_trip(trip_id, requirement)

    await trips_collection().update_one(
        {"_id": trip_id},
        {"$set": {
            "requirement": requirement.model_dump(mode="json"),
            "last_plan": response.model_dump(mode="json"),
            "updated_at": now_iso,
        }},
        upsert=True,
    )
    assistant_summary = (
        f"Here's a {response.trip_summary.duration_days}-day plan for {response.trip_summary.destination}. "
        f"Estimated total: {response.budget.total} {response.budget.currency} "
        f"({'over' if response.budget.over_budget else 'within'} budget by "
        f"{abs(response.budget.remaining)})."
    )
    await messages_collection().insert_one(
        Message(trip_id=trip_id, role="assistant", content=assistant_summary).model_dump(mode="json")
    )
    return response

