"""
Deterministic budget engine.

Per the spec: "Budget = deterministic calculator, not LLM arithmetic."
The agent NEVER computes totals itself — it selects candidate flights /
hotels / activities, and this pure-Python function does the math.
"""
from app.models.schemas import BudgetBreakdown, NormalizedResult

# Rough per-day heuristics used only when the LLM/tools don't surface an
# explicit activities/transport figure. Kept obviously-labelled as estimates.
DEFAULT_DAILY_FOOD_PER_PERSON = 1500.0  # in trip currency, adjust via FX upstream
DEFAULT_DAILY_TRANSPORT = 800.0
DEFAULT_DAILY_OTHER = 300.0


def calculate_budget(
    *,
    travelers: int,
    duration_days: int,
    total_budget: float,
    currency: str,
    selected_flight: NormalizedResult | None,
    selected_hotel: NormalizedResult | None,
    selected_activities: list[NormalizedResult],
    nights: int | None = None,
) -> BudgetBreakdown:
    nights = nights if nights is not None else max(duration_days - 1, 1)

    flight_cost = (selected_flight.price or 0) * travelers if selected_flight else 0.0
    hotel_cost = (selected_hotel.price or 0) * nights if selected_hotel else 0.0
    food_cost = DEFAULT_DAILY_FOOD_PER_PERSON * travelers * duration_days
    activities_cost = sum((a.price or 0) for a in selected_activities)
    transport_cost = DEFAULT_DAILY_TRANSPORT * duration_days
    other_cost = DEFAULT_DAILY_OTHER * duration_days

    total = flight_cost + hotel_cost + food_cost + activities_cost + transport_cost + other_cost
    remaining = total_budget - total

    return BudgetBreakdown(
        flight=round(flight_cost, 2),
        hotel=round(hotel_cost, 2),
        food=round(food_cost, 2),
        activities=round(activities_cost, 2),
        transport=round(transport_cost, 2),
        other=round(other_cost, 2),
        total=round(total, 2),
        remaining=round(remaining, 2),
        currency=currency,
        over_budget=total > total_budget,
    )
