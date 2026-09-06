import { useEffect, useState } from "react";
import { api } from "./api/client";
import { BudgetDashboard } from "./components/BudgetDashboard";
import { ChatPanel } from "./components/ChatPanel";
import { ItineraryTimeline } from "./components/ItineraryTimeline";
import { MapView } from "./components/MapView";
import { ResultList } from "./components/ResultList";
import { TripSummaryCard } from "./components/TripSummaryCard";
import { WeatherWidget } from "./components/WeatherWidget";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "itinerary", label: "Itinerary" },
  { key: "flights", label: "Flights" },
  { key: "hotels", label: "Hotels" },
  { key: "restaurants", label: "Restaurants" },
  { key: "attractions", label: "Attractions" },
  { key: "map", label: "Map" },
];

function newLocalMessage(role, content) {
  return {
    id: crypto.randomUUID(),
    trip_id: "",
    role,
    content,
    created_at: new Date().toISOString(),
  };
}

export default function App() {
  const [tripId, setTripId] = useState(null);
  const [plan, setPlan] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(()=>{
    console.log(plan)
  },[plan])

  async function handleSend(message) {
    setError(null);
    setMessages((prev) => [...prev, newLocalMessage("user", message)]);
    setIsLoading(true);
    try {
      const response = tripId ? await api.chat(tripId, message) : await api.createTrip(message);
      console.log(response)
      setTripId(response.trip_id);
      setPlan(response);
      console.log(response)
      if(response.assistant_message!==null){
        console.log("null")
        const assistantText = response.assistant_message
        setMessages((prev) => [...prev, newLocalMessage("assistant", assistantText)]);
      }
      else{
        console.log("not null")
        const assistantText = response.needs_clarification
        ? response.needs_clarification
        : `Here's a ${response.trip_summary.duration_days}-day plan for ${response.trip_summary.destination}. Estimated total: ${response.budget.currency} ${response.budget.total.toLocaleString()} (${response.budget.over_budget ? "over" : "within"} budget).`;
        setMessages((prev) => [...prev, newLocalMessage("assistant", assistantText)]);
      }
      
      
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Something went wrong reaching the planning backend.";
      setError(msg);
      setMessages((prev) => [...prev, newLocalMessage("assistant", `⚠ ${msg}`)]);
    } finally {
      setIsLoading(false);
    }
  }

  const hasPlan = plan && !plan.needs_clarification && plan.trip_summary.destination;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-paper">
      <aside className="w-[380px] shrink-0 border-r border-line">
        <ChatPanel messages={messages} onSend={handleSend} isLoading={isLoading} hasTrip={!!tripId} />
      </aside>

      <main className="flex-1 overflow-y-auto">
        {!hasPlan ? (
          <div className="flex h-full flex-col items-center justify-center px-8 text-center">
            <p className="font-display text-3xl font-semibold text-ink">Where to, and with what budget?</p>
            <p className="mt-2 max-w-md text-sm text-ink-soft/60">
              Describe your trip in the chat — destination, dates, travelers, and budget — and Wayfarer will
              assemble a priced, day-by-day itinerary from live-style flight, hotel, and activity data.
            </p>
            {error && <p className="mt-4 text-sm text-coral">{error}</p>}
          </div>
        ) : (
          <div className="mx-auto max-w-4xl space-y-6 px-8 py-8">
            <TripSummaryCard summary={plan.trip_summary} />

            {plan.assumptions.length > 0 && (
              <div className="rounded-xl border border-amber/30 bg-amber/5 px-4 py-3 text-xs text-ink-soft/80">
                <span className="font-semibold text-amber">Assumptions made:</span>{" "}
                {plan.assumptions.join(" · ")}
              </div>
            )}

            <nav className="flex flex-wrap gap-1 border-b border-line">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setActiveTab(t.key)}
                  className={`rounded-t-lg px-4 py-2 text-sm font-medium transition ${
                    activeTab === t.key
                      ? "border-b-2 border-teal text-ink"
                      : "text-ink-soft/50 hover:text-ink-soft"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>

            <div>
              {activeTab === "overview" && (
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                  <BudgetDashboard budget={plan.budget} />
                  <WeatherWidget weather={plan.weather} />
                </div>
              )}
              {activeTab === "itinerary" && <ItineraryTimeline days={plan.itinerary} />}
              {activeTab === "flights" && (
                <ResultList title="Flights" results={plan.flights} priceSuffix=" / person" />
              )}
              {activeTab === "hotels" && (
                <ResultList title="Hotels" results={plan.hotels} priceSuffix=" / night" />
              )}
              {activeTab === "restaurants" && (
                <ResultList title="Restaurants" results={plan.restaurants} priceSuffix=" / person" />
              )}
              {activeTab === "attractions" && (
                <ResultList title="Attractions" results={plan.attractions} priceSuffix=" / person" />
              )}
              {activeTab === "map" && (
                <MapView hotels={plan.hotels} attractions={plan.attractions} destination={plan.trip_summary.destination} />
              )}
            </div>

            <p className="pt-2 text-[11px] text-ink-soft/40">
              Data sources this session: {plan.sources.join(", ")}
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
