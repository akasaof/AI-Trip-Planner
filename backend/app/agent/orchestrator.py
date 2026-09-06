
from __future__ import annotations
import json
from datetime import date, timedelta
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.agent.extraction import extract_requirement

from app.config import get_settings
from app.db import messages_collection, tool_results_collection, trips_collection
from app.models.schemas import (
    BudgetBreakdown,
    ItineraryDay,
    ItineraryItem,
    Message,
    NormalizedResult,
    TripPlanResponse,
    TripRequirement,
    TripSummary,
)
from app.tools import ALL_TOOLS
from app.tools.rag_tool import rag_search
from app.utils.budget import calculate_budget


from app.agent.data_gathering import gather_tool_data
from app.agent.itinerary_builder import select_for_budget,build_itinerary_skeleton
from app.agent.enrichment import enrich_with_summaries
from app.agent.intent import classify_intent

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from app.config import get_settings

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


def _weather_for_days(requirement: TripRequirement, weather_results: list[NormalizedResult]) -> dict:
    """Map available weather results onto day numbers so the itinerary
    builder (and UI) can show per-day forecasts."""
    by_date = {}
    for w in weather_results:
        d = w.details.get("date")
        if d:
            by_date[d] = w.details
    return by_date


async def generate_conversation_response(
    user_message: str,
    last_plan: dict
) -> str:
    print("Inside funnction")
    prompt = f"""
You are a helpful travel assistant.

The user already has the following trip plan:

{last_plan}

The user now says:
"{user_message}"

Respond naturally to the user's message using the trip plan as context.

Rules:
- Keep the response short and conversational.
- Do not rebuild or modify the trip plan.
- Do not invent information that is not present in the plan.
- If the user asks something unrelated to the trip, answer briefly.
- Return only the response text.

Response:
"""
    settings = get_settings()
    llm = ChatGroq(
             model=settings.groq_model,
             api_key=settings.groq_api_key,
             temperature=0,
             max_tokens=100,
         )
     
    messages = [
             SystemMessage(content=prompt),
             HumanMessage(content=user_message),
         ]
    response = await llm.ainvoke(prompt)
    
    return response.content.strip()






async def plan_trip(trip_id: str, requirement: TripRequirement,intent:str,user_message:str,trip_doc:dict) -> TripPlanResponse:
    """Runs steps 4-11 of the workflow. Assumes requirement is already
    validated as complete (step 3 happened in the caller)."""
    rag_context = rag_search.invoke({"query": f"{requirement.destination} transport culture weather best time"})

    normalized = await gather_tool_data(requirement, trip_id)

    selected_flight, selected_hotel, selected_activities = select_for_budget(normalized)
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

    skeleton = build_itinerary_skeleton(requirement, normalized, selected_flight, selected_hotel)
    built = await enrich_with_summaries(requirement, skeleton)

    end_date = None
    if requirement.start_date and requirement.duration_days:
        end_date = requirement.start_date + timedelta(days=requirement.duration_days - 1)

    sources = sorted({r.source.value for group in normalized.values() for r in group} | {"cached"})
    result=await generate_conversation_response(user_message,trip_doc) if intent == "conversation" else None
    

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
        assistant_message= await generate_conversation_response(user_message,trip_doc) if intent == "conversation" else None
    )
    return response


async def handle_user_message(trip_id: str, user_message: str) -> TripPlanResponse:
    """Top-level entry point used by both POST /trips (first message) and
    POST /trips/{id}/chat (follow-ups)."""
    print("Message",user_message)
    intent = await classify_intent(user_message)
    print("intent",intent)
    trip_doc = await trips_collection().find_one({"_id": trip_id})
    print(trip_doc['last_plan'])
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
            assistant_message= await generate_conversation_response(user_message,trip_doc['last_plan']) if intent == "conversation" else None
        )
        await messages_collection().insert_one(
            Message(trip_id=trip_id, role="assistant", content=clarification).model_dump(mode="json")
        )
        return response
    
    response = await plan_trip(trip_id, requirement,intent,user_message,trip_doc['last_plan'])

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

