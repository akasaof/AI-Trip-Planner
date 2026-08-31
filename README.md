# Wayfarer — AI Trip Planner (POC)

Implements the requirements in `AI_Trip_Planner_POC_Requirements_Compact.docx`,
with changes from the original spec: **MongoDB** instead of PostgreSQL,
**Groq (`openai/gpt-oss-120b` via `langchain_groq.ChatGroq`)** as the LLM
instead of Gemini/OpenAI/Claude, a **plain JavaScript** React frontend
(no TypeScript), and **fully live data** — every tool calls a real free
API; nothing is mocked.

```
React (JS)  →  FastAPI  →  LangChain agent (ChatGroq)  →  RAG (TF-IDF)
                                              ↓
        live tools: Travelpayouts (flights/hotels) · Geoapify (restaurants/
        attractions) · OpenWeatherMap (weather) · OpenRouteService
        (distance) · open.er-api.com (currency)
                                              ↓
                          deterministic budget + itinerary assembly (pure Python)
                                              ↓
                                      MongoDB
```

## What's live, and two honest limitations

Every tool calls a real free-tier API — see **Getting your free API
keys** below. Weather (OpenWeatherMap), distances
(OpenRouteService/Google Maps), and currency conversion
(open.er-api.com) return genuinely live, on-demand numbers.

**Flights and hotels (Travelpayouts/Aviasales/Hotellook)** are real live
data, but it's *cached, recently-observed* pricing — what travelers have
actually searched or booked recently on that route or for that hotel —
not an on-demand live availability quote for your exact date. No free
API provides true real-time GDS-style search; Travelpayouts is the
closest free option after Amadeus's self-service portal was permanently
decommissioned (2026-07-17 — existing self-service keys were disabled;
only their sales-contract Enterprise tier remains). Every such result is
flagged via `details.cached_recent_fare` / `details.cached_recent_rate`.

**Restaurant and attraction prices (Geoapify)** are the other exception:
no free public API anywhere exposes real menu prices or ticket prices —
that data is commercial and requires a paid partnership (Viator,
GetYourGuide, etc.). Geoapify gives real, live venue data (name,
address) sourced from OpenStreetMap, but the cost figure shown is a
category-based estimate, flagged via `details.price_estimated`. OSM data
also doesn't carry star ratings, so `rating` is left blank rather than
invented.

Both cases are flagged in the UI via the "Estimated" vs "Live" source
badge on every result. Nothing is ever presented as a guaranteed live
price when it isn't.

If a required API key is missing, or a provider genuinely has no data
for a route/city/date, the corresponding tool returns an empty list —
never a fabricated result. The itinerary is built deterministically in
Python from whatever real data came back (see below), so the app still
produces a complete, correctly-dated day-by-day plan even before you've
added every key.

The **budget is never computed by the LLM** — `app/utils/budget.py` is a
plain, deterministic function called after gathering tool results, per
the spec's "Budget = deterministic calculator, not LLM arithmetic" rule.
The **itinerary structure is also deterministic** (`app/agent/
orchestrator.py::_build_itinerary_skeleton`): flights, hotel nights, and
meals/attractions are assigned to days in plain Python from the real
tool data, so it can never come back empty or truncated the way an
LLM-generated nested JSON structure can on a rate-limited free tier. The
LLM's role is deliberately narrowed to what it's actually good at and
what's low-risk to fail: writing a one-sentence summary per day. If that
enrichment call fails for any reason, the itinerary still renders with
plain, factual generated summaries instead.

## Prerequisites

- Python 3.11+
- Node.js 18+
- A Groq API key (you already have this)
- MongoDB running locally (you're using MongoDB Compass — the default
  `.env` already points at `mongodb://localhost:27017`, so no changes
  needed unless your local instance uses a different port/auth)
- Free API keys for the live providers — see below

## Backend setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: add GROQ_API_KEY and whichever provider keys you've signed up for
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive API docs once it's running.

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Visit `http://localhost:5173`.

## Try it

In the chat panel:

> Plan a 5-day trip to Dubai for 2 people under ₹1,50,000, leaving from
> Chennai in mid-November. We like adventure and sightseeing.

If any required field (destination, duration, travelers, budget, or
start date) is missing, the agent asks for it instead of guessing.
Once a trip exists, send a follow-up like "add a beach day" — the agent
preserves everything you already told it and only updates what changed.

## Getting your free API keys

| Provider | Used for | Sign up | Notes |
|---|---|---|---|
| **Travelpayouts** | Flights + hotels | https://www.travelpayouts.com → sign up (free) → **Tools → API** for your token, your **Marker** is on your account dashboard | Free, self-serve, no credit card. Put them in `TRAVELPAYOUTS_TOKEN` / `TRAVELPAYOUTS_MARKER`. Data is cached/recently-observed pricing, not a live on-demand quote — see the honest-limitations section above. Replaces Amadeus, whose self-service portal was permanently decommissioned 2026-07-17. |
| **Geoapify Places API** | Restaurants + attractions | https://myprojects.geoapify.com → sign up → create a project → **API Keys** tab | Free tier: 3,000 requests/day, no credit card. Put the key in `GEOAPIFY_API_KEY`. (Earlier versions of this README pointed at Foursquare — Foursquare deprecated its free real-time search API in mid-2026 and replaced it with a paid, quota-limited product, so this project uses Geoapify's OpenStreetMap-backed Places API instead. Venue name/address are live; Geoapify/OSM data doesn't include star ratings, so `rating` is left blank rather than invented, same honesty rule as the price estimate below.) |
| **OpenWeatherMap** | Weather | https://openweathermap.org/api → sign up → API keys tab | Free tier. New keys can take up to ~2 hours to activate. Put it in `OPENWEATHER_API_KEY`. Note: the free tier only gives *current* conditions, not a forecast for a date months away — see the comment in `app/tools/weather.py`. |
| **OpenRouteService** | Driving distance between places | https://openrouteservice.org/dev/#/signup → confirm email → API keys are on your dashboard | Free tier, no credit card. Put it in `OPENROUTESERVICE_API_KEY`. |
| **open.er-api.com** | Currency conversion | Nothing to do — no signup, no key | Completely free, used automatically. |
| *(optional)* Google Maps Distance Matrix | Alternative to OpenRouteService, and powers the real embedded map on the frontend's Map tab | https://console.cloud.google.com → enable "Distance Matrix API" + "Maps Embed API" → create an API key | Requires a Google Cloud billing account (has a monthly free credit). Only needed if you want the live map embed or prefer Google's distance data over OpenRouteService's. Set `GOOGLE_MAPS_API_KEY` in `backend/.env` for distance, and `VITE_GOOGLE_MAPS_API_KEY` in `frontend/.env` for the embed. |

You don't need all of them to start — the app runs and produces a
complete itinerary with just `GROQ_API_KEY` set (everything else simply
returns no data for that category until you add its key).

## Project layout

```
backend/
  app/
    main.py            FastAPI app, CORS, lifespan (Mongo connect/close)
    config.py           env-driven settings (all provider keys)
    db.py                Motor (async MongoDB) client + collection helpers
    models/schemas.py   Pydantic schemas: requirement, normalized results,
                         budget, itinerary, trip document, API request/response
    agent/
      extraction.py      NL message -> structured TripRequirement
                         (context-preserving; dates parsed with dateutil,
                         not forced through a strict LLM date schema)
      orchestrator.py    the workflow: extract -> validate -> RAG ->
                         deterministic live-tool calls -> deterministic
                         budget -> deterministic itinerary skeleton ->
                         optional LLM day-summary enrichment -> persist
      prompts.py         system prompts encoding the "never invent data" rule
    tools/               flight_search, hotel_search (Travelpayouts),
                         restaurant_search, attraction_search (Geoapify),
                         weather_lookup (OpenWeatherMap), map_distance
                         (OpenRouteService/Google), currency_convert
                         (open.er-api.com), rag_search (local TF-IDF) —
                         each a LangChain @tool calling a real live API
      travelpayouts_client.py  shared IATA code resolution (autocomplete)
      geoapify_client.py       shared geocoding + Places search
    rag/
      retriever.py       TF-IDF ingest/chunk/index/retrieve pipeline (no
                         external embedding API required)
      data/*.md          curated destination guides (Dubai, Bali — add
                         more .md files here to extend the corpus)
    routers/trips.py     POST /api/trips, GET /{id}, POST /{id}/chat,
                         POST /{id}/plan, GET /{id}/messages|budget|weather|map
    utils/budget.py      the deterministic budget calculator
frontend/
  src/
    api/client.js         fetch wrapper around the backend
    components/          ChatPanel, TripSummaryCard, ResultList (flights/
                         hotels/restaurants/attractions), WeatherWidget,
                         BudgetDashboard, ItineraryTimeline, MapView, SourceBadge
    App.jsx               tabbed dashboard layout wiring chat -> plan state
```

## Testing notes

This was built and verified in a sandboxed environment without outbound
access to Groq, Travelpayouts, Geoapify, OpenWeatherMap, OpenRouteService, or
a local MongoDB instance — so the full pipeline (deterministic tool
calls → normalization → deterministic budget math → deterministic
itinerary assembly → persistence → follow-up context preservation) was
exercised end-to-end against an in-memory MongoDB mock, with each live
tool verified to degrade gracefully (empty result, no crash) when its
key isn't configured, since that's exactly the network condition in this
sandbox. Once you add real keys, the actual API responses will flow
through the same, already-tested normalization path — but it's worth
doing one real run to confirm data shapes match what each provider
currently returns (external APIs occasionally change response fields).
