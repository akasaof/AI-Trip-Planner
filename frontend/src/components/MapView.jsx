const MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

export function MapView({ hotels, attractions, destination }) {
  if (MAPS_KEY) {
    const query = encodeURIComponent(destination);
    return (
      <div className="overflow-hidden rounded-2xl border border-line shadow-sm">
        <iframe
          title="Trip map"
          className="h-80 w-full border-0"
          loading="lazy"
          src={`https://www.google.com/maps/embed/v1/place?key=${MAPS_KEY}&q=${query}`}
        />
      </div>
    );
  }

  const pins = [...hotels.map((h) => ({ ...h, type: "Hotel" })), ...attractions.map((a) => ({ ...a, type: "Attraction" }))];

  return (
    <div className="rounded-2xl border border-line bg-white p-5 shadow-sm">
      <div className="flex items-baseline justify-between">
        <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink-soft/70">Map</h3>
        <span className="text-[11px] text-ink-soft/50">Set VITE_GOOGLE_MAPS_API_KEY for a live map</span>
      </div>
      {pins.length === 0 ? (
        <p className="mt-3 text-sm text-ink-soft/50">No locations yet.</p>
      ) : (
        <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {pins.map((p, idx) => (
            <li key={idx} className="flex items-center gap-2 rounded-lg border border-line/70 px-3 py-2 text-sm">
              <span className={`h-2 w-2 shrink-0 rounded-full ${p.type === "Hotel" ? "bg-teal" : "bg-coral"}`} />
              <span className="truncate text-ink">{p.name}</span>
              <span className="ml-auto shrink-0 text-[10px] uppercase text-ink-soft/50">{p.type}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
