"use client";

import { useMemo, useState } from "react";

import { useWorkspace } from "@/components/layout/workspace-provider";
import { SignalsTable } from "@/components/signals/signals-table";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import type { SignalRefreshResult } from "@/types";

export default function SignalsPage() {
  const workspace = useWorkspace();
  const { data, loading, error, reload } = useApi(() => api.getSignals(workspace.signalProviderType), [workspace.signalProviderType]);
  const [symbolFilter, setSymbolFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [strategyFilter, setStrategyFilter] = useState("");
  const [refreshResult, setRefreshResult] = useState<SignalRefreshResult | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.filter((signal) => {
      const symbolMatch = !symbolFilter || signal.symbol.toLowerCase().includes(symbolFilter.toLowerCase());
      const actionMatch = !actionFilter || signal.action === actionFilter;
      const strategyMatch = !strategyFilter || (signal.strategy_slug || "").includes(strategyFilter);
      return symbolMatch && actionMatch && strategyMatch;
    });
  }, [actionFilter, data, strategyFilter, symbolFilter]);

  async function handleGenerate() {
    setRefreshing(true);
    try {
      const result = await api.generateSignals(workspace.signalProviderType);
      setRefreshResult(result);
      reload();
    } catch (err) {
      setRefreshResult({
        provider_type: workspace.signalProviderType,
        status: "error",
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

  if (loading || !data) return <div className="text-sm text-slate-400">Loading signals...</div>;
  if (error) return <div className="text-sm text-rose-300">Signals failed to load: {error}</div>;

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
              Market data updates: <span className="text-slate-100">{String(refreshResult.market_report.snapshots_updated ?? 0)}</span>
            </div>
            <div>
              News articles added: <span className="text-slate-100">{String(refreshResult.news_report.articles_added ?? 0)}</span>
            </div>
          </div>
        </div>
      ) : null}

      <div className="rounded-2xl border border-border bg-panel/90 px-4 py-3 text-sm text-slate-300 shadow-panel">
        This page shows the common signal pool for the current workspace model. Older template/demo-era signal rows are intentionally hidden, and refresh now reports whether data updated, no candidates qualified, or the provider itself is blocking generation.
      </div>

      <div className="grid gap-3 rounded-2xl border border-border bg-panel/90 p-4 shadow-panel md:grid-cols-3">
        <input value={symbolFilter} onChange={(event) => setSymbolFilter(event.target.value)} placeholder="Filter by symbol" className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
        <select value={actionFilter} onChange={(event) => setActionFilter(event.target.value)} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
          <option value="">All actions</option>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
          <option value="hold">Hold</option>
        </select>
        <input value={strategyFilter} onChange={(event) => setStrategyFilter(event.target.value)} placeholder="Filter by strategy slug" className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
      </div>

      {filtered.length ? (
        <SignalsTable signals={filtered} />
      ) : (
        <div className="rounded-2xl border border-border bg-panel/90 p-6 text-sm text-slate-300 shadow-panel">
          No real signals are stored yet for <span style={{ color: workspace.theme.primary }}>{workspace.label}</span>. Refresh after market data and provider connectivity are available.
        </div>
      )}
    </div>
  );
}

function bannerStyle(status: string) {
  if (status === "success") {
    return {
      borderColor: "rgba(52, 211, 153, 0.28)",
      backgroundColor: "rgba(16, 185, 129, 0.12)",
    };
  }
  if (status === "blocked") {
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
