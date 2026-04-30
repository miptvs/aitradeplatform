"use client";

import { useEffect, useMemo, useState } from "react";

import { SignalTraceDialog } from "@/components/signals/signal-trace-dialog";
import { useWorkspace } from "@/components/layout/workspace-provider";
import { SignalsTable } from "@/components/signals/signals-table";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import type { Signal, SignalRefreshResult, SignalTrace } from "@/types";

export default function SignalsPage() {
  const workspace = useWorkspace();
  const { data, loading, error, reload } = useApi(async () => {
    const [signals, diagnostics] = await Promise.all([
      api.getSignals(workspace.signalProviderType),
      api.getSignalDiagnostics(workspace.signalProviderType),
    ]);
    return { signals, diagnostics };
  }, [workspace.signalProviderType]);
  const [symbolFilter, setSymbolFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [strategyFilter, setStrategyFilter] = useState("");
  const [refreshResult, setRefreshResult] = useState<SignalRefreshResult | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [signalTrace, setSignalTrace] = useState<SignalTrace | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState<string | null>(null);
  const [approvingLane, setApprovingLane] = useState<"live" | "simulation" | null>(null);

  useEffect(() => {
    const interval = window.setInterval(() => reload(), 60_000);
    return () => window.clearInterval(interval);
  }, [reload]);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.signals.filter((signal) => {
      const symbolMatch = !symbolFilter || signal.symbol.toLowerCase().includes(symbolFilter.toLowerCase());
      const actionMatch = !actionFilter || signal.action === actionFilter;
      const strategyMatch = !strategyFilter || (signal.strategy_slug || "").includes(strategyFilter);
      return symbolMatch && actionMatch && strategyMatch;
    });
  }, [actionFilter, data, strategyFilter, symbolFilter]);

  async function handleGenerate() {
    setRefreshing(true);
    try {
      const result = await api.generateSignals(workspace.signalProviderType, { forceRefresh: true });
      setRefreshResult(result);
      reload();
    } catch (err) {
      setRefreshResult({
        provider_type: workspace.signalProviderType,
        status: "error",
        run_type: "manual",
        observed_at: new Date().toISOString(),
        created_signal_ids: [],
        created_count: 0,
        message: err instanceof Error ? err.message : "Signal refresh failed.",
        detail: null,
        market_report: {},
        news_report: {},
      });
    } finally {
      setRefreshing(false);
    }
  }

  async function handleOpenTrace(signal: Signal) {
    setSelectedSignal(signal);
    setTraceLoading(true);
    setTraceError(null);
    try {
      const trace = await api.getSignalTrace(signal.id);
      setSignalTrace(trace);
    } catch (err) {
      setTraceError(err instanceof Error ? err.message : "Signal trace failed to load.");
      setSignalTrace(null);
    } finally {
      setTraceLoading(false);
    }
  }

  async function handleApprove(lane: "live" | "simulation") {
    if (!selectedSignal) return;
    try {
      setApprovingLane(lane);
      const decision =
        lane === "live" ? await api.approveLiveSignal(selectedSignal.id) : await api.approveSimulationSignal(selectedSignal.id);
      setRefreshResult((current) => ({
        provider_type: current?.provider_type || workspace.signalProviderType,
        status: "success",
        run_type: current?.run_type || "manual",
        observed_at: current?.observed_at || new Date().toISOString(),
        created_signal_ids: current?.created_signal_ids || [],
        created_count: current?.created_count || 0,
        message: decision.reason,
        detail: `${decision.symbol} moved into the ${lane === "live" ? "live review queue" : "simulation review queue"}.`,
        market_report: current?.market_report || {},
        news_report: current?.news_report || {},
      }));
      await handleOpenTrace(selectedSignal);
      reload();
    } catch (err) {
      setTraceError(err instanceof Error ? err.message : `Failed to approve signal for ${lane}.`);
    } finally {
      setApprovingLane(null);
    }
  }

  if (loading || !data) return <div className="text-sm text-slate-400">Loading signals...</div>;
  if (error) return <div className="text-sm text-rose-300">Signals failed to load: {error}</div>;

  const lastRun = refreshResult || data.diagnostics;
  const detailLaneStatuses = signalTrace?.signal?.lane_statuses || selectedSignal?.lane_statuses || {};
  const liveLaneReady = (detailLaneStatuses.live || "candidate") === "candidate";
  const simulationLaneReady = (detailLaneStatuses.simulation || "candidate") === "candidate";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Signals</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100">Real model-backed signal candidates</h1>
          <div className="mt-2 text-sm text-slate-400">
            Active signal model: <span style={{ color: workspace.theme.primary }}>{workspace.signalProviderType}</span>
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={refreshing}
          className="rounded-xl border px-4 py-2 text-sm hover:opacity-90"
          style={{
            borderColor: workspace.theme.accentBorder,
            backgroundColor: workspace.theme.accentSurface,
            color: workspace.theme.primary,
            opacity: refreshing ? 0.65 : 1,
          }}
        >
          {refreshing ? "Refreshing..." : "Refresh signals"}
        </button>
      </div>

      {refreshResult ? (
        <div
          className="rounded-2xl border px-4 py-3 text-sm shadow-panel"
          style={bannerStyle(refreshResult.status)}
        >
          <div className="font-medium text-slate-100">{refreshResult.message}</div>
          {refreshResult.detail ? <div className="mt-1 text-xs text-slate-300">{refreshResult.detail}</div> : null}
          <div className="mt-3 grid gap-2 text-xs text-slate-300 md:grid-cols-3">
            <div>
              Created signals: <span className="text-slate-100">{refreshResult.created_count}</span>
            </div>
            <div>
              Market data new / updated:{" "}
              <span className="text-slate-100">
                {String(refreshResult.market_report.snapshots_created ?? 0)} / {String(refreshResult.market_report.snapshots_updated ?? 0)}
              </span>
            </div>
            <div>
              News articles added: <span className="text-slate-100">{String(refreshResult.news_report.articles_added ?? 0)}</span>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <RunStatCard label="Last run" value={formatRunType(lastRun.run_type)} hint={lastRun.observed_at ? `${formatDateTime(lastRun.observed_at, { includeYear: false })} · auto every 5m` : "Not recorded yet"} />
        <RunStatCard label="Run status" value={lastRun.status} hint={lastRun.provider_type} />
        <RunStatCard label="New signals" value={String(lastRun.created_count ?? 0)} hint="Created in that run" />
        <RunStatCard label="News added" value={String(lastRun.news_report?.articles_added ?? 0)} hint="RSS articles in that run" />
        <RunStatCard
          label="Market data"
          value={`${String(lastRun.market_report?.snapshots_created ?? 0)} / ${String(lastRun.market_report?.snapshots_updated ?? 0)}`}
          hint="New / updated snapshots"
        />
      </div>

      <div className="rounded-2xl border border-border bg-panel/90 px-4 py-3 text-sm text-slate-300 shadow-panel">
        This page shows the common signal pool for the current workspace model. Older template/demo-era signal rows are intentionally hidden, and refresh now reports whether data updated, no candidates qualified, or the provider itself is blocking generation.
      </div>

      <div className="grid gap-3 rounded-2xl border border-border bg-panel/90 p-4 shadow-panel md:grid-cols-3">
        <input value={symbolFilter} onChange={(event) => setSymbolFilter(event.target.value)} placeholder="Filter by symbol" className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
        <select value={actionFilter} onChange={(event) => setActionFilter(event.target.value)} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
          <option value="">All actions</option>
          <option value="buy">Buy / Open</option>
          <option value="sell">Sell / Close</option>
          <option value="close_long">Close long</option>
          <option value="reduce_long">Reduce long</option>
          <option value="short">Short</option>
          <option value="cover_short">Cover short</option>
          <option value="hold">Hold</option>
        </select>
        <input value={strategyFilter} onChange={(event) => setStrategyFilter(event.target.value)} placeholder="Filter by strategy slug" className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
      </div>

      {filtered.length ? (
        <SignalsTable signals={filtered} onSelectSignal={handleOpenTrace} />
      ) : (
        <div className="rounded-2xl border border-border bg-panel/90 p-6 text-sm text-slate-300 shadow-panel">
          No real signals are stored yet for <span style={{ color: workspace.theme.primary }}>{workspace.label}</span>. Refresh after market data and provider connectivity are available.
        </div>
      )}

      <SignalTraceDialog
        open={Boolean(selectedSignal)}
        signal={selectedSignal}
        trace={signalTrace}
        loading={traceLoading}
        error={traceError}
        onClose={() => {
          setSelectedSignal(null);
          setSignalTrace(null);
          setTraceError(null);
        }}
        actions={
          <>
            <button
              type="button"
              disabled={!selectedSignal || !liveLaneReady || approvingLane !== null}
              onClick={() => handleApprove("live")}
              className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-100 hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-60"
              title={liveLaneReady ? "Send this shared signal into the guarded live review workflow." : "This signal already has a live-lane outcome."}
            >
              {approvingLane === "live" ? "Sending..." : liveLaneReady ? "Send to live review" : `Live: ${detailLaneStatuses.live || "queued"}`}
            </button>
            <button
              type="button"
              disabled={!selectedSignal || !simulationLaneReady || approvingLane !== null}
              onClick={() => handleApprove("simulation")}
              className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-100 hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
              title={simulationLaneReady ? "Approve this shared signal for the simulation workflow." : "This signal already has a simulation-lane outcome."}
            >
              {approvingLane === "simulation"
                ? "Approving..."
                : simulationLaneReady
                  ? "Approve for simulation"
                  : `Simulation: ${detailLaneStatuses.simulation || "queued"}`}
            </button>
          </>
        }
      />
    </div>
  );
}

function RunStatCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-border bg-panel/90 px-4 py-3 shadow-panel">
      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold capitalize text-slate-100">{value}</div>
      <div className="mt-1 truncate text-xs text-slate-400">{hint}</div>
    </div>
  );
}

function formatRunType(value?: string | null) {
  if (!value || value === "none") return "No run";
  return value === "automatic" ? "Automatic" : "Manual";
}

function bannerStyle(status: string) {
  if (status === "success") {
    return {
      borderColor: "rgba(52, 211, 153, 0.28)",
      backgroundColor: "rgba(16, 185, 129, 0.12)",
    };
  }
  if (status === "blocked" || status === "noop" || status === "warn" || status === "warning") {
    return {
      borderColor: "rgba(245, 158, 11, 0.28)",
      backgroundColor: "rgba(245, 158, 11, 0.12)",
    };
  }
  if (status === "error") {
    return {
      borderColor: "rgba(244, 63, 94, 0.28)",
      backgroundColor: "rgba(225, 29, 72, 0.12)",
    };
  }
  return {
    borderColor: "rgba(59, 130, 246, 0.24)",
    backgroundColor: "rgba(30, 64, 175, 0.12)",
  };
}
