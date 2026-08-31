import { SourceBadge } from "./SourceBadge";

export function WeatherWidget({ weather }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5 shadow-sm">
      <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink-soft/70">Weather</h3>
      {weather.length === 0 ? (
        <p className="mt-3 text-sm text-ink-soft/50">No forecast yet.</p>
      ) : (
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {weather.map((w, idx) => {
            const d = w.details;
            const high = d.temp_c_high ?? d.temp_c;
            const low = d.temp_c_low;
            const condition = d.condition ?? "";
            return (
              <div key={idx} className="rounded-xl border border-line/70 p-3">
                <p className="text-xs text-ink-soft/60">{d.date ?? w.location}</p>
                <p className="data-figure mt-1 text-lg font-semibold text-ink">
                  {high != null ? `${Math.round(high)}°` : "—"}
                  {low != null && <span className="text-ink-soft/50"> / {Math.round(low)}°</span>}
                </p>
                <p className="text-xs text-ink-soft/70">{condition}</p>
                <div className="mt-2">
                  <SourceBadge source={w.source} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
