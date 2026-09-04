from app.models.schemas import (ItineraryDay,ItineraryItem,NormalizedResult,TripRequirement,)

from datetime import timedelta




def _round_robin(pool: list[NormalizedResult], index: int) -> NormalizedResult | None:
    if not pool:
        return None
    return pool[index % len(pool)]



def select_for_budget(normalized: dict[str, list[NormalizedResult]]):
    flights = sorted(normalized.get("flight", []), key=lambda r: r.price or 0)
    hotels = sorted(normalized.get("hotel", []), key=lambda r: r.price or 0)
    attractions = normalized.get("attraction", [])[:4]
    selected_flight = flights[0] if flights else None
    selected_hotel = hotels[0] if hotels else None
    return selected_flight, selected_hotel, attractions



def build_itinerary_skeleton(
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
