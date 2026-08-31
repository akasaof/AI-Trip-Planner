const STYLES = {
  live: "bg-teal/10 text-teal-dark border-teal/30",
  mock: "bg-amber/10 text-amber border-amber/40",
  cached: "bg-ink/5 text-ink-soft border-ink/15",
  estimated: "bg-ink/5 text-ink-soft border-ink/15",
};

const LABELS = {
  live: "Live",
  mock: "Estimated",
  cached: "Curated",
  estimated: "Estimated",
};

export function SourceBadge({ source }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${STYLES[source]}`}
      title={
        source === "live"
          ? "Fetched from a live provider API"
          : source === "cached"
          ? "Retrieved from curated destination knowledge (RAG)"
          : "No live provider configured — simulated for this POC"
      }
    >
      {LABELS[source]}
    </span>
  );
}
