import { SourceBadge } from "./SourceBadge";

const CATEGORY_ICON = {
  activity: "◆",
  meal: "●",
  transport: "→",
  hotel: "⌂",
};

export function ItineraryTimeline({ days }) {
  if (days.length === 0) {
    return (
      <div className="rounded-2xl border border-line bg-white p-8 text-center text-sm text-ink-soft/50 shadow-sm">
        Your day-by-day plan will appear here once the trip is built.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {days.map((day) => (
        <div key={day.day_number} className="ticket-stub relative rounded-2xl border border-line bg-white px-6 pb-8 pt-5 shadow-sm">
          <span className="ticket-notch -left-[9px]" />
          <span className="ticket-notch -right-[9px]" />

          <div className="flex items-baseline justify-between">
            <div>
              <p className="font-display text-lg font-semibold text-ink">Day {day.day_number}</p>
              {day.date && <p className="data-figure text-xs text-ink-soft/60">{day.date}</p>}
            </div>
            <p className="data-figure text-sm font-semibold text-ink-soft/80">
              Daily cost: {day.daily_cost.toLocaleString()}
            </p>
          </div>

          {day.summary && <p className="mt-2 text-sm text-ink-soft/70">{day.summary}</p>}

          <ul className="mt-4 space-y-3">
            {day.items.map((item) => (
              <li key={item.id} className="flex items-start gap-3">
                <span className="mt-0.5 w-5 shrink-0 text-center text-teal-dark">
                  {CATEGORY_ICON[item.category] ?? "•"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {item.time && <span className="data-figure text-xs text-ink-soft/60">{item.time}</span>}
                    <span className="text-sm font-medium text-ink">{item.title}</span>
                    <SourceBadge source={item.source} />
                  </div>
                  {item.notes && <p className="mt-0.5 text-xs text-ink-soft/60">{item.notes}</p>}
                </div>
                <span className="data-figure shrink-0 text-xs text-ink-soft/70">
                  {item.currency} {item.estimated_cost.toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
