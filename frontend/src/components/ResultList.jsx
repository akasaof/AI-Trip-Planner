import { SourceBadge } from "./SourceBadge";

export function ResultList({ title, results, priceSuffix = "", emptyLabel }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-5 shadow-sm">
      <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink-soft/70">{title}</h3>
      {results.length === 0 ? (
        <p className="mt-3 text-sm text-ink-soft/50">{emptyLabel ?? "Nothing found yet."}</p>
      ) : (
        <ul className="mt-3 divide-y divide-line">
          {results.map((r, idx) => (
            <li key={idx} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{r.name}</p>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-ink-soft/60">
                  {r.location && <span className="truncate">{r.location}</span>}
                  {r.rating != null && (
                    <span className="data-figure">★ {r.rating.toFixed(1)}</span>
                  )}
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                {r.price != null && (
                  <span className="data-figure text-sm font-semibold text-ink">
                    {r.currency} {r.price.toLocaleString()}
                    {priceSuffix}
                  </span>
                )}
                <SourceBadge source={r.source} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
