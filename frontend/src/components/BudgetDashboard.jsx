const CATEGORIES = [
  { key: "flight", label: "Flights", color: "bg-teal" },
  { key: "hotel", label: "Hotel", color: "bg-teal-dark" },
  { key: "food", label: "Food", color: "bg-amber" },
  { key: "activities", label: "Activities", color: "bg-coral" },
  { key: "transport", label: "Transport", color: "bg-ink-soft" },
  { key: "other", label: "Other", color: "bg-line" },
];

export function BudgetDashboard({ budget }) {
  const max = Math.max(budget.total, 1);
  return (
    <div className="rounded-2xl border border-line bg-white p-5 shadow-sm">
      <div className="flex items-baseline justify-between">
        <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink-soft/70">Budget</h3>
        <span
          className={`data-figure text-xs font-semibold ${
            budget.over_budget ? "text-coral" : "text-teal-dark"
          }`}
        >
          {budget.over_budget ? "Over by " : "Remaining "}
          {budget.currency} {Math.abs(budget.remaining).toLocaleString()}
        </span>
      </div>

      <p className="data-figure mt-2 text-3xl font-semibold text-ink">
        {budget.currency} {budget.total.toLocaleString()}
      </p>

      <div className="mt-4 flex h-3 w-full overflow-hidden rounded-full bg-paper">
        {CATEGORIES.map(({ key, color }) => {
          const value = budget[key];
          const width = (value / max) * 100;
          return width > 0 ? (
            <div key={key} className={color} style={{ width: `${width}%` }} title={`${key}: ${value}`} />
          ) : null;
        })}
      </div>

      <ul className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
        {CATEGORIES.map(({ key, label, color }) => (
          <li key={key} className="flex items-center gap-2 text-xs text-ink-soft/70">
            <span className={`h-2 w-2 rounded-full ${color}`} />
            {label}
            <span className="data-figure ml-auto text-ink">{budget[key].toLocaleString()}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
