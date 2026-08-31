"""
Endpoints per Section 5 of the spec:
POST /api/trips, GET /api/trips/{id}, POST /api/trips/{id}/chat,
POST /api/trips/{id}/plan, GET .../messages, /budget, /weather, /map
"""
from datetime import date

from fastapi import APIRouter, HTTPException

from app.agent.orchestrator import handle_user_message
from app.db import messages_collection, trips_collection
from app.models.schemas import ChatRequest, CreateTripRequest, TripPlanResponse, TripRequirement, new_id
from app.tools.travelpayouts_client import resolve_iata
router = APIRouter(prefix="/api/trips", tags=["trips"])


@router.post("", response_model=TripPlanResponse)
async def create_trip(payload: CreateTripRequest):
    result = await resolve_iata("Chennai")
    print(result)
    trip_id = new_id()
    await trips_collection().insert_one({
        "_id": trip_id,
        "user_id": "demo-user",
        "requirement": TripRequirement().model_dump(mode="json"),
        "last_plan": None,
        "created_at": date.today().isoformat(),
        "updated_at": date.today().isoformat(),
    })
    return await handle_user_message(trip_id, payload.message)


@router.get("/{trip_id}")
async def get_trip(trip_id: str):
    trip = await trips_collection().find_one({"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    trip["id"] = trip.pop("_id")
    return trip


@router.post("/{trip_id}/chat", response_model=TripPlanResponse)
async def chat(trip_id: str, payload: ChatRequest):
    trip = await trips_collection().find_one({"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return await handle_user_message(trip_id, payload.message)


@router.post("/{trip_id}/plan", response_model=TripPlanResponse)
async def replan(trip_id: str):
    """Re-run planning against the currently-known requirement fields
    (e.g. after the frontend nudges a preference without new chat text)."""
    trip = await trips_collection().find_one({"_id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return await handle_user_message(trip_id, "Please re-generate the itinerary with the current trip details.")


@router.get("/{trip_id}/messages")
async def get_messages(trip_id: str):
    cursor = messages_collection().find({"trip_id": trip_id}).sort("created_at", 1)
    return [doc async for doc in cursor]


@router.get("/{trip_id}/budget")
async def get_budget(trip_id: str):
    trip = await trips_collection().find_one({"_id": trip_id})
    if not trip or not trip.get("last_plan"):
        raise HTTPException(status_code=404, detail="No plan yet for this trip")
    return trip["last_plan"]["budget"]


@router.get("/{trip_id}/weather")
async def get_weather(trip_id: str):
    trip = await trips_collection().find_one({"_id": trip_id})
    if not trip or not trip.get("last_plan"):
        raise HTTPException(status_code=404, detail="No plan yet for this trip")
    return trip["last_plan"]["weather"]


@router.get("/{trip_id}/map")
async def get_map(trip_id: str):
    trip = await trips_collection().find_one({"_id": trip_id})
    if not trip or not trip.get("last_plan"):
        raise HTTPException(status_code=404, detail="No plan yet for this trip")
    plan = trip["last_plan"]
    return {
        "destination": plan["trip_summary"]["destination"],
        "attractions": plan["attractions"],
        "hotels": plan["hotels"],
        "restaurants": plan["restaurants"],
    }
