import type { ExtractedEvent, NewsArticle } from "@/types";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatDateTime } from "@/lib/utils";

export function NewsList({ news, events }: { news: NewsArticle[]; events: ExtractedEvent[] }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">News Flow</div>
        {news.length ? (
          <div className="space-y-3">
            {news.map((item) => (
              <div key={item.id} className="rounded-xl border border-border bg-black/20 p-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <a href={item.url} target="_blank" rel="noreferrer" className="font-semibold text-slate-100 hover:text-cyan-100 hover:underline">
                      {item.title}
                    </a>
                    <div className="mt-1 text-xs text-slate-400">
                      {item.source} • {formatDateTime(item.published_at)} • {item.affected_symbols.join(", ") || "Unmapped"}
                    </div>
                  </div>
                  <StatusBadge status={item.sentiment || "neutral"} />
                </div>
                <div className="mt-2 text-sm text-slate-300">{item.summary}</div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                  <span className="rounded-full border border-border px-2 py-1">Impact {(item.impact_score || 0).toFixed(2)}</span>
                  {item.analysis_metadata?.feed_url ? <span className="rounded-full border border-border px-2 py-1">RSS</span> : null}
                  {item.provider_type ? <span className="rounded-full border border-border px-2 py-1">{item.provider_type}</span> : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-black/20 p-4 text-sm text-slate-400">
            No stored articles yet. Use the refresh controls above to fetch live RSS headlines or backfill the last 24 hours.
          </div>
        )}
      </div>
      <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Extracted Events</div>
        {events.length ? (
          <div className="space-y-3">
            {events.map((event) => (
              <div key={event.id} className="rounded-xl border border-border bg-black/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-slate-100">{event.event_type}</div>
                  <div className="text-xs text-slate-400">{Math.round(event.impact_score * 100)} impact</div>
                </div>
                <div className="mt-1 text-sm text-slate-300">{event.summary}</div>
                <div className="mt-2 text-xs text-slate-400">Symbol: {event.symbol || "-"}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-black/20 p-4 text-sm text-slate-400">
            No extracted events yet. Fresh news refreshes will populate sentiment and event tags here.
          </div>
        )}
      </div>
    </div>
  );
}
