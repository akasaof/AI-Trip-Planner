# AI Trip Planner

A conversational travel planner. Describe a trip in plain English — destination, dates, travelers, budget — and get back a priced, day-by-day itinerary with flights, hotels, restaurants, attractions, weather, and a budget breakdown. Follow-up messages ("make it 3 days", "add more beaches") update the same trip.

The backend is a FastAPI service that combines an LLM (Groq, via LangChain) with real travel data APIs. The frontend is a React app with a chat panel on the left and the generated plan on the right.

## Features

- **Natural-language planning** – the LLM extracts structured trip details (destination, duration, travelers, budget, start date, preferences) from free text and merges them with what it already knows about the trip.
- **Clarifying questions** – if destination, duration, travelers, budget, or start date is missing, the assistant asks for it instead of guessing.
- **Conversation memory** – each trip is stored in MongoDB, so later messages modify the existing plan rather than starting over.
- **Intent detection** – each chat message is classified as a trip modification or general conversation about the current plan.
- **Live data where possible** – flights and hotels (Travelpayouts), restaurants and attractions (Geoapify), weather (OpenWeatherMap), distances (Google Maps or OpenRouteService), and currency conversion (open.er-api.com).
- **Honest data labelling** – every result carries a `source` of `live`, `cached`, `estimated`, or `mock`, and the UI shows which sources were used. Estimates are never presented as live quotes.
- **Deterministic budget** – totals are computed in code, never by the LLM.
- **Destination knowledge base (RAG)** – curated guides retrieved with TF-IDF, no embedding API key needed.
- **Tabbed UI** – Overview (budget + weather), Itinerary, Flights, Hotels, Restaurants, Attractions, Map.

## Tech stack

| Layer | Tech |
| --- | --- |
| Backend | Python, FastAPI, Uvicorn, Pydantic v2 |
| LLM | LangChain + Groq (default model `openai/gpt-oss-120b`) |
| Database | MongoDB via Motor (async) |
| RAG | scikit-learn TF-IDF + cosine similarity |
| HTTP client | httpx |
| Frontend | React 18, Vite 5, Tailwind CSS 3 |

## How it works

Each message goes through the same pipeline (`backend/app/agent/orchestrator.py`):

1. **Classify intent** – trip modification vs. conversation (`intent.py`). On failure it defaults to modification, so a real instruction is never silently ignored.
2. **Extract requirements** – an LLM structured-output call turns the message into a `TripRequirement`, merged with the previously stored one. Dates are extracted as free text and parsed with `dateutil` (`extraction.py`).
3. **Check completeness** – if required fields are missing, return a clarifying question and stop.
4. **Retrieve destination context** – RAG lookup over the guides in `backend/app/rag/data/`.
5. **Gather tool data** – flights, hotels, restaurants, attractions, and weather are all called deterministically (not LLM-driven). Each call is logged to MongoDB, and one tool failing never blocks the others (`data_gathering.py`).
6. **Select and budget** – the cheapest flight and hotel and the first few attractions are chosen, and the budget is calculated (`itinerary_builder.py`, `utils/budget.py`).
7. **Build the itinerary** – a day-by-day skeleton (flight, hotel, lunch, attraction, dinner) is assembled from the tool results, so an itinerary always exists even if the LLM fails.
8. **Enrich** – an optional LLM pass writes a one-sentence summary per day and a few assumptions (`enrichment.py`). If it fails, the generic summaries stay.
9. **Persist and respond** – the plan is saved and returned as a single `TripPlanResponse` JSON payload for the frontend.

### Fallbacks

| Data | Primary source | Fallback |
| --- | --- | --- |
| Flights | Travelpayouts cached fares (`live`) | LLM fare estimate (`estimated`) |
| Hotels | Travelpayouts/Hotellook cache (`live`) | Built-in baseline rates (`cached`) |
| Attractions | Geoapify venues (`live`, prices estimated) | Generic LLM category suggestions, no invented venue names (`estimated`) |
| Restaurants | Geoapify venues (`live`, prices estimated) | – |
| Weather | OpenWeatherMap current conditions | – (empty if no key) |

Flight and hotel prices are recently observed cached rates, not live quotes for your exact dates. Weather is today's conditions at the destination, used as a seasonal proxy rather than a forecast for your trip dates.

## Project structure

```
.
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py              # FastAPI app, CORS, health check
│       ├── config.py            # Settings loaded from .env
│       ├── db.py                # MongoDB (Motor) connection + indexes
│       ├── agent/               # Pipeline: intent, extraction, data gathering,
│       │   │                    #   itinerary builder, enrichment, orchestrator
│       │   └── prompts/         # System prompts
│       ├── models/schemas.py    # Pydantic models (requirements, results, plan)
│       ├── routers/trips.py     # REST endpoints
│       ├── tools/               # flights, hotels, restaurants, attractions,
│       │                        #   weather, maps, currency, rag_search
│       ├── rag/                 # TF-IDF retriever + data/*.md destination guides
│       └── utils/budget.py      # Deterministic budget calculator
└── frontend/
    ├── package.json
    ├── .env.example
    └── src/
        ├── App.jsx              # Layout, tabs, chat handling
        ├── api/client.js        # Backend API wrapper
        └── components/          # ChatPanel, ItineraryTimeline, BudgetDashboard,
                                 #   WeatherWidget, MapView, ResultList, ...
```

## Getting started

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- A running MongoDB instance (local, or a MongoDB Atlas connection string)
- A [Groq](https://console.groq.com) API key (required)
- Optional API keys for live data (see below)

### 1. Clone

```bash
git clone https://github.com/akasaof/AI-Trip-Planner.git
cd AI-Trip-Planner
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then edit .env (see Configuration)
uvicorn app.main:app --reload --port 8000
```

The API is now at http://localhost:8000, with interactive docs at http://localhost:8000/docs.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5173.

### 4. Try it

In the chat, send something like:

> Plan a 5-day trip to Dubai for 2 people starting November 15 with a budget of ₹1,50,000. I'm flying from Chennai.

## Configuration

### Backend (`backend/.env`)

| Variable | Required | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | Groq API key for all LLM calls |
| `GROQ_MODEL` | No | Default `openai/gpt-oss-120b` |
| `MONGODB_URI` | Yes | e.g. `mongodb://localhost:27017` or an Atlas URI. **Set this explicitly**: leaving the line blank in `.env` overrides the built-in default with an empty value. |
| `MONGODB_DB_NAME` | No | Default `trip_planner` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins. Default `http://localhost:5173` |
| `LLM_TEMPERATURE` | No | Default `0.2` |
| `LLM_MAX_TOKENS` | No | Default `3500`. Groq's free tier caps prompt + completion at about 8000 tokens per request |
| `LLM_TOOL_LOOP_MAX_TOKENS` | No | Default `700` |
| `TRAVELPAYOUTS_TOKEN` | For flights/hotels | Travelpayouts (Aviasales/Hotellook) API token. Without it, flight search returns nothing and hotels use baseline estimates |
| `TRAVELPAYOUTS_MARKER` | No | Your Travelpayouts partner ID |
| `GEOAPIFY_API_KEY` | For restaurants/attractions | Geoapify Places API key (free tier, no card) |
| `OPENWEATHER_API_KEY` | For weather | OpenWeatherMap API key |
| `OPENROUTESERVICE_API_KEY` | No | Distance lookups via OpenRouteService |
| `GOOGLE_MAPS_API_KEY` | No | Alternative for distance lookups; takes priority over OpenRouteService if set |
| `REQUEST_TIMEOUT_SECONDS` | No | Default `12` |

The app starts with only `GROQ_API_KEY` and MongoDB configured, but plans will be thin without the provider keys: missing keys mean empty results or labelled estimates for that category.

### Frontend (`frontend/.env`)

| Variable | Description |
| --- | --- |
| `VITE_API_BASE_URL` | Backend URL. Default `http://localhost:8000` |
| `VITE_GOOGLE_MAPS_API_KEY` | Optional. Enables an embedded Google map on the Map tab; otherwise a list is shown |

## API

All routes are under `/api/trips`.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/trips` | Create a trip from a first message and return the plan (or a clarifying question) |
| `GET` | `/api/trips/{trip_id}` | Fetch the stored trip document |
| `POST` | `/api/trips/{trip_id}/chat` | Send a follow-up message |
| `POST` | `/api/trips/{trip_id}/plan` | Re-generate the plan from the current requirements |
| `GET` | `/api/trips/{trip_id}/messages` | Conversation history |
| `GET` | `/api/trips/{trip_id}/budget` | Budget breakdown of the latest plan |
| `GET` | `/api/trips/{trip_id}/weather` | Weather results of the latest plan |
| `GET` | `/api/trips/{trip_id}/map` | Destination, attractions, hotels, and restaurants for mapping |
| `GET` | `/api/health` | Health check |

Example:

```bash
curl -X POST http://localhost:8000/api/trips \
  -H "Content-Type: application/json" \
  -d '{"message": "3 days in Bali for 2 from Chennai, starting 10 December, budget 120000 INR"}'
```

### Data stored in MongoDB

- `trips` – requirements and the latest plan per trip
- `messages` – chat history
- `tool_results` – a log of every tool call, with arguments, results, and errors

## Notes and limitations

- Amounts default to **INR**, and the departure city defaults to **Chennai** when none is given.
- The budget calculator uses fixed per-day estimates for food, local transport, and miscellaneous costs (see `backend/app/utils/budget.py`).
- The built-in RAG knowledge base currently covers **Bali** and **Dubai**. Add more by dropping Markdown guides into `backend/app/rag/data/`.
- Users are not authenticated; all trips are stored under a single `demo-user`.
- Flight and hotel prices come from cached market data and are indicative only. Nothing here books anything.
