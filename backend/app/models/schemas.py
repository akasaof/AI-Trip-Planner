"""
Pydantic schemas shared across the extraction chain, tools, agent
orchestrator, API routers, and Mongo persistence layer.

`DataSource` is the mechanism the spec calls for to distinguish
estimated vs. cached (RAG) vs. live provider data, so the UI can label
everything honestly and the agent is never allowed to silently invent
numbers.
"""
from __future__ import annotations

import uuid
import datetime as dt
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class DataSource(str, Enum):
    LIVE = "live"       # returned by a real, currently-configured provider API
    MOCK = "mock"       # simulated/estimated — no live provider configured
    CACHED = "cached"   # served from RAG / prior tool_results cache
    ESTIMATED = "estimated"  # derived heuristically (e.g. deterministic budget math)


# --------------------------------------------------------------------------
# Requirement extraction (Section 3 of the spec)
# --------------------------------------------------------------------------

class TripRequirement(BaseModel):
    destination: Optional[str] = None
    country: Optional[str] = None
    duration_days: Optional[int] = None
    travelers: Optional[int] = None
    budget: Optional[float] = None
    currency: Optional[str] = "INR"
    departure_city: Optional[str] = None
    start_date: Optional[dt.date] = None
    end_date: Optional[dt.date] = None
    preferences: list[str] = Field(default_factory=list)
    trip_type: Optional[str] = None
   

    def missing_required_fields(self) -> list[str]:
        """Dates are required for any live search — everything else can be
        inferred/defaulted, but we never invent dates."""
        missing = []
        for field in ("destination", "duration_days", "travelers", "budget"):
            if getattr(self, field) in (None, "", 0):
                missing.append(field)
        if self.start_date is None:
            missing.append("start_date")
        return missing


# --------------------------------------------------------------------------
# Normalized tool result schema (Section 6 of the spec)
# --------------------------------------------------------------------------

class NormalizedResult(BaseModel):
    """Every provider tool (real or mock) returns a list of these, so the
    agent and UI never see provider-specific shapes."""
    kind: str  # "flight" | "hotel" | "restaurant" | "attraction" | "weather" | "distance"
    name: str
    location: Optional[str] = None
    rating: Optional[float] = None
    price: Optional[float] = None
    currency: str = "INR"
    source: DataSource = DataSource.MOCK
    details: dict = Field(default_factory=dict)


class ToolCallRecord(BaseModel):
    id: str = Field(default_factory=new_id)
    trip_id: str
    tool_name: str
    arguments: dict
    results: list[NormalizedResult] = Field(default_factory=list)
    source: DataSource = DataSource.MOCK
    error: Optional[str] = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


# --------------------------------------------------------------------------
# Budget (Section 5 — deterministic calculator, never LLM arithmetic)
# --------------------------------------------------------------------------

class BudgetBreakdown(BaseModel):
    flight: float = 0
    hotel: float = 0
    food: float = 0
    activities: float = 0
    transport: float = 0
    other: float = 0
    total: float = 0
    remaining: float = 0
    currency: str = "INR"
    over_budget: bool = False


# --------------------------------------------------------------------------
# Itinerary
# --------------------------------------------------------------------------

class ItineraryItem(BaseModel):
    id: str = Field(default_factory=new_id)
    time: Optional[str] = None  # e.g. "09:00"
    title: str
    category: str  # "activity" | "meal" | "transport" | "hotel"
    location: Optional[str] = None
    estimated_cost: float = 0
    currency: str = "INR"
    source: DataSource = DataSource.MOCK
    notes: Optional[str] = None


class ItineraryDay(BaseModel):
    day_number: int
    date: Optional[dt.date] = None
    summary: Optional[str] = None
    weather: Optional[dict] = None
    items: list[ItineraryItem] = Field(default_factory=list)
    daily_cost: float = 0


class TripSummary(BaseModel):
    destination: str
    country: Optional[str] = None
    duration_days: int
    travelers: int
    start_date: Optional[dt.date] = None
    end_date: Optional[dt.date] = None
    trip_type: Optional[str] = None


class TripPlanResponse(BaseModel):
    """The single React-ready JSON payload returned by /plan and /chat,
    matching the standard schema from Section 5 of the spec."""
    trip_id: str
    trip_summary: TripSummary
    flights: list[NormalizedResult] = Field(default_factory=list)
    hotels: list[NormalizedResult] = Field(default_factory=list)
    restaurants: list[NormalizedResult] = Field(default_factory=list)
    attractions: list[NormalizedResult] = Field(default_factory=list)
    weather: list[NormalizedResult] = Field(default_factory=list)
    budget: BudgetBreakdown
    itinerary: list[ItineraryDay] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    needs_clarification: Optional[str] = None
    assistant_message: Optional[str] = None


# --------------------------------------------------------------------------
# Conversation / persistence
# --------------------------------------------------------------------------

class Message(BaseModel):
    id: str = Field(default_factory=new_id)
    trip_id: str
    role: str  # "user" | "assistant"
    content: str
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class TripDocument(BaseModel):
    """The document stored in the `trips` Mongo collection."""
    id: str = Field(default_factory=new_id)
    user_id: str = "demo-user"
    requirement: TripRequirement = Field(default_factory=TripRequirement)
    last_plan: Optional[TripPlanResponse] = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class CreateTripRequest(BaseModel):
    message: str


class ChatRequest(BaseModel):
    message: str



