export function TripSummaryCard({ summary }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-line bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-ink-soft/60">Destination</p>
          <p className="font-display text-2xl font-semibold text-ink">
            {summary.destination}
            {summary.country ? <span className="text-ink-soft/50">, {summary.country}</span> : null}
          </p>
        </div>
        <div className="flex gap-8">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-ink-soft/60">Dates</p>
            <p className="data-figure text-sm text-ink">
              {summary.start_date ?? "TBD"} — {summary.end_date ?? "TBD"}
            </p>
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-ink-soft/60">Duration</p>
            <p className="data-figure text-sm text-ink">{summary.duration_days} days</p>
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-ink-soft/60">Travelers</p>
            <p className="data-figure text-sm text-ink">{summary.travelers}</p>
          </div>
        </div>
      </div>
      <div
        className="h-2 w-full opacity-70 [--tw-barcode-color:#12172B] bg-barcode"
        aria-hidden="true"
      />
    </div>
  );
}
