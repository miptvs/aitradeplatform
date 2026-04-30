"use client";

import { useState } from "react";

import { NewsList } from "@/components/news/news-list";
import { StatsCard } from "@/components/stats-card";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

export default function NewsPage() {
  const { data, loading, error, reload } = useApi(async () => {
    const [news, events, diagnostics] = await Promise.all([api.getNews(), api.getEvents(), api.getNewsDiagnostics()]);
    return { news, events, diagnostics };
  });
  const [refreshing, setRefreshing] = useState<"latest" | "force" | null>(null);
  const [message, setMessage] = useState<{ tone: "success" | "warning" | "error"; text: string } | null>(null);
  const [backfillHours, setBackfillHours] = useState("24");

  async function handleRefresh(kind: "latest" | "force") {
    try {
      setRefreshing(kind);
      const result =
        kind === "force"
          ? await api.refreshNews({ force_refresh: true, backfill_hours: Number(backfillHours) })
          : await api.refreshNews({ force_refresh: false });
      setMessage({ tone: result.feeds_failed ? "warning" : "success", text: result.message });
      await reload();
    } catch (refreshError) {
      setMessage({ tone: "error", text: refreshError instanceof Error ? refreshError.message : "News refresh failed." });
    } finally {
      setRefreshing(null);
    }
  }

  if (loading || !data) return <div className="text-sm text-slate-400">Loading market intelligence...</div>;
  if (error) return <SeverityBanner tone="error" message={`News failed to load: ${error}`} />;

  const diagnostics = data.diagnostics;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">News / Market Intelligence</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100">Real news ingestion, event extraction, and feed diagnostics</h1>
          <div className="mt-2 text-sm text-slate-400">The refresh summary now explains whether feeds were stale, duplicated, failed, or simply had nothing new that survived dedupe.</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => handleRefresh("latest")}
            disabled={refreshing !== null}
            className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {refreshing === "latest" ? "Refreshing RSS..." : "Refresh latest RSS"}
          </button>
          <button
            type="button"
            onClick={() => handleRefresh("force")}
            disabled={refreshing !== null}
            className="rounded-xl border border-amber-400/30 bg-amber-400/10 px-4 py-2 text-sm text-amber-100 hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {refreshing === "force" ? "Backfilling..." : `Force refresh ${backfillHours}h`}
          </button>
          <label className="flex items-center gap-2 rounded-xl border border-border bg-panel/70 px-3 py-2 text-sm text-slate-300">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Backfill</span>
            <select
              value={backfillHours}
              onChange={(event) => setBackfillHours(event.target.value)}
              disabled={refreshing !== null}
              className="bg-transparent text-sm text-slate-200 outline-none"
            >
              <option value="6">6h</option>
              <option value="12">12h</option>
              <option value="24">24h</option>
              <option value="48">48h</option>
              <option value="72">72h</option>
            </select>
          </label>
        </div>
      </div>

      {message ? <SeverityBanner tone={message.tone} message={message.text} /> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatsCard
          label="Last run"
          value={formatRunType(diagnostics.run_type)}
          kind="text"
          detail={formatDateTime(diagnostics.observed_at, { includeYear: false, fallback: "Not recorded yet" })}
        />
        <StatsCard label="Feeds checked" value={diagnostics.feeds_checked} kind="text" />
        <StatsCard label="New news" value={diagnostics.articles_added} kind="text" detail="RSS articles added in that run" />
        <StatsCard label="Duplicates skipped" value={diagnostics.duplicates_skipped} kind="text" />
        <StatsCard label="Older skipped" value={diagnostics.date_skipped} kind="text" />
        <StatsCard label="Feeds failed" value={diagnostics.feeds_failed} kind="text" />
      </div>

      <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Latest refresh diagnostics</div>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <InfoRow label="Last status" value={humanRefreshMessage(diagnostics)} />
          <InfoRow label="Read articles since" value={formatDateTime(diagnostics.cutoff)} />
          <InfoRow label="Last successful fetch" value={formatOptionalDateTime(diagnostics.last_successful_fetch_time)} />
          <InfoRow label="Newest article found" value={formatOptionalDateTime(diagnostics.latest_seen_published_at)} />
        </div>
        {!diagnostics.feed_reports.length ? (
          <div className="mt-4 rounded-2xl border border-dashed border-border bg-black/20 px-4 py-3 text-sm text-slate-400">
            No feed-level diagnostics have been recorded yet. Run a refresh to capture per-feed counts, sample titles, duplicate skips, and parse failures.
          </div>
        ) : null}
      </div>

      <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Per-feed results</div>
        <div className="grid gap-3">
          {diagnostics.feed_reports.map((report) => (
            <div key={report.feed_url} className="rounded-2xl border border-border bg-black/20 p-4">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div>
                  <div className="font-semibold text-slate-100">{report.feed_label}</div>
                  <div className="text-xs text-slate-500">{report.feed_url}</div>
                </div>
                <div className="rounded-full border border-border px-3 py-1 text-xs uppercase tracking-[0.16em] text-slate-300">{report.status}</div>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-4">
                <InfoRow label="Fetched" value={String(report.fetched_count)} />
                <InfoRow label="Added" value={String(report.added_count)} />
                <InfoRow label="Duplicates" value={String(report.duplicate_count)} />
                <InfoRow label="Older" value={String(report.date_skipped_count)} />
              </div>
              {report.sample_titles.length ? (
                <div className="mt-3 text-sm text-slate-300">
                  <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Sample titles</div>
                  <div className="mt-2 space-y-1">
                    {report.sample_titles.map((title) => (
                      <div key={title}>{title}</div>
                    ))}
                  </div>
                </div>
              ) : null}
              {report.error ? <div className="mt-3 text-sm text-rose-300">{report.error}</div> : null}
            </div>
          ))}
        </div>
      </div>

      <NewsList news={data.news} events={data.events} />
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-black/20 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm text-slate-200">{value}</div>
    </div>
  );
}

function SeverityBanner({ tone, message }: { tone: "success" | "warning" | "error"; message: string }) {
  const styles = {
    success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-100",
    warning: "border-amber-500/30 bg-amber-500/10 text-amber-100",
    error: "border-rose-500/30 bg-rose-500/10 text-rose-100",
  }[tone];
  const label = tone === "success" ? "OK" : tone === "warning" ? "Warning" : "Error";
  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm shadow-panel ${styles}`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-80">{label}</div>
      <div className="mt-1">{message}</div>
    </div>
  );
}

function formatRunType(value?: string | null) {
  if (!value || value === "none") return "No run";
  return value === "automatic" ? "Automatic" : "Manual";
}

function formatOptionalDateTime(value?: string | null) {
  return formatDateTime(value, { fallback: "Not recorded yet" });
}

function humanRefreshMessage(diagnostics: {
  articles_added: number;
  feeds_checked: number;
  feeds_failed: number;
  duplicates_skipped: number;
  date_skipped: number;
  force_refresh: boolean;
}) {
  const mode = diagnostics.force_refresh ? "Backfill" : "Refresh";
  const parts = [
    `${mode} found ${diagnostics.articles_added} new article${diagnostics.articles_added === 1 ? "" : "s"}`,
    `checked ${diagnostics.feeds_checked} feed${diagnostics.feeds_checked === 1 ? "" : "s"}`,
  ];
  if (diagnostics.duplicates_skipped) {
    parts.push(`skipped ${diagnostics.duplicates_skipped} duplicate${diagnostics.duplicates_skipped === 1 ? "" : "s"}`);
  }
  if (diagnostics.date_skipped) {
    parts.push(`ignored ${diagnostics.date_skipped} older item${diagnostics.date_skipped === 1 ? "" : "s"}`);
  }
  if (diagnostics.feeds_failed) {
    parts.push(`${diagnostics.feeds_failed} feed${diagnostics.feeds_failed === 1 ? "" : "s"} failed`);
  }
  return `${parts.join(", ")}.`;
}
