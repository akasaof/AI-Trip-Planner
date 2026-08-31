import { useState } from "react";

export function ChatPanel({ messages, onSend, isLoading, hasTrip }) {
  const [draft, setDraft] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!draft.trim() || isLoading) return;
    onSend(draft.trim());
    setDraft("");
  }

  return (
    <div className="flex h-full flex-col bg-ink text-paper">
      <div className="border-b border-white/10 px-5 py-4">
        <p className="font-display text-lg font-semibold tracking-tight">Wayfarer</p>
        <p className="text-xs text-white/50">Tell it where, when, who, and how much.</p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-white/70">
            Try: <span className="italic">"Plan a 5-day trip to Dubai for 2 people under ₹1,50,000, leaving from Chennai in mid-November. We like adventure and sightseeing."</span>
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`max-w-[90%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              m.role === "user"
                ? "ml-auto bg-teal text-ink"
                : "mr-auto bg-white/8 text-paper border border-white/10"
            }`}
          >
            {m.content}
          </div>
        ))}
        {isLoading && (
          <div className="mr-auto flex items-center gap-1.5 rounded-2xl border border-white/10 bg-white/8 px-4 py-3">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber [animation-delay:300ms]" />
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-white/10 p-4">
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            rows={2}
            placeholder={hasTrip ? "Ask for a change, e.g. 'add a beach day'" : "Describe your trip..."}
            className="flex-1 resize-none rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-sm text-paper placeholder:text-white/35 focus:border-teal focus:outline-none"
          />
          <button
            type="submit"
            disabled={isLoading || !draft.trim()}
            className="rounded-lg bg-teal px-4 py-2.5 text-sm font-medium text-ink transition hover:bg-teal-dark disabled:cursor-not-allowed disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
