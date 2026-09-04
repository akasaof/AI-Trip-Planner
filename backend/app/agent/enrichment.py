from pydantic import BaseModel, Field
from app.config import get_settings

from app.agent.prompts.planning import PLANNING_SYSTEM_PROMPT
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
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
import json


class _DaySummary(BaseModel):
    day_number: int
    summary: str

class _ItineraryBuildOutput(BaseModel):
    itinerary: list[ItineraryDay] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


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

async def enrich_with_summaries(
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
