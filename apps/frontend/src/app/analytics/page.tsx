"use client";

import { useState } from "react";

import { EquityCurveChart } from "@/components/charts/equity-curve-chart";
import { PnlBarChart } from "@/components/charts/pnl-bar-chart";
import { useWorkspace } from "@/components/layout/workspace-provider";
import { StatsCard } from "@/components/stats-card";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatCurrency, formatPct } from "@/lib/utils";
import type { SimulationAccount } from "@/types";

export default function AnalyticsPage() {
  const workspace = useWorkspace();
  const [analyticsMode, setAnalyticsMode] = useState<"simulation" | "live">("simulation");
  const [selectedSimulationAccountId, setSelectedSimulationAccountId] = useState("");
  const { data, loading, error } = useApi(async () => {
    const simulationAccounts = await api.getSimulationAccounts();
    const scopedSimulationAccountId =
      analyticsMode === "simulation"
        ? resolveSimulationAccountId(simulationAccounts, workspace.simulationProviderType, selectedSimulationAccountId)
        : undefined;
    const [overview, combinedCurve, simVsLive, modelComparison] = await Promise.all([
      api.getAnalyticsOverview({ mode: analyticsMode, simulationAccountId: scopedSimulationAccountId }),
      api.getEquityCurve(analyticsMode, scopedSimulationAccountId),
      api.getSimulationVsLive(),
      api.getModelComparison()
    ]);
    return { overview, combinedCurve, simVsLive, modelComparison, simulationAccounts, scopedSimulationAccountId };
  }, [analyticsMode, selectedSimulationAccountId, workspace.simulationProviderType]);

  if (loading || !data) return <div className="text-sm text-slate-400">Loading analytics...</div>;
  if (error) return <div className="text-sm text-rose-300">Analytics failed to load: {error}</div>;
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
  const hasWinsWithoutLosses = data.overview.average_loss === 0 && data.overview.average_win > 0;
  const scopeLabel = analyticsMode === "live" ? "Live Trading" : "Simulation";
  const visibleModelRows = analyticsMode === "simulation" ? data.modelComparison : [];
  const selectedSimulationAccount = data.simulationAccounts.find((account) => account.id === data.scopedSimulationAccountId);

  return (
    <div className="min-w-0 space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Analytics</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100">Performance, risk, and attribution</h1>
          {analyticsMode === "simulation" ? (
            <div className="mt-1 text-sm text-slate-400">
              Scope: {selectedSimulationAccount ? selectedSimulationAccount.name : "No simulation account"}
            </div>
          ) : null}
        </div>
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
          {analyticsMode === "simulation" ? (
            <select
              value={data.scopedSimulationAccountId || ""}
              onChange={(event) => setSelectedSimulationAccountId(event.target.value)}
              className="min-w-0 rounded-xl border border-border bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              {data.simulationAccounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          ) : null}
          <div className="flex rounded-xl border border-border bg-black/20 p-1">
            {(["simulation", "live"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setAnalyticsMode(mode)}
                className={`rounded-lg px-3 py-2 text-xs uppercase tracking-[0.16em] transition ${analyticsMode === mode ? "bg-cyan-400/10 text-cyan-100" : "text-slate-400 hover:text-slate-200"}`}
              >
                {mode === "live" ? "Live Trading" : "Simulation"}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatsCard label="Total return" value={data.overview.total_return} kind="percent" />
        <StatsCard label="Sharpe" value={data.overview.sharpe} kind="number" />
        <StatsCard label="Sortino" value={data.overview.sortino} kind="number" />
        <StatsCard label="Max drawdown" value={data.overview.max_drawdown} kind="percent" />
        <StatsCard label="Average win" value={data.overview.average_win} />
        <StatsCard label="Average loss" value={formatAverageLoss(data.overview.average_loss, data.overview.average_win)} kind={hasWinsWithoutLosses ? "text" : "currency"} />
        <StatsCard label="Profit factor" value={formatProfitFactor(data.overview.profit_factor, data.overview.average_loss, data.overview.average_win)} kind="text" />
        <StatsCard label="Confidence correlation" value={data.overview.confidence_correlation} kind="number" />
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <EquityCurveChart data={data.combinedCurve} title={`${scopeLabel} equity curve`} />
        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Simulation vs Live</div>
          <div className="mt-4 grid gap-3">
            <MetricRow label="Live return" value={formatPct(data.simVsLive.live_return)} tone={data.simVsLive.live_return >= 0 ? "positive" : "negative"} />
            <MetricRow label="Simulation return" value={formatPct(data.simVsLive.simulation_return)} tone={data.simVsLive.simulation_return >= 0 ? "positive" : "negative"} />
            <MetricRow label="Delta" value={formatPct(data.simVsLive.delta_return)} tone={data.simVsLive.delta_return >= 0 ? "positive" : "negative"} />
          </div>
        </div>
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-3">
        <PnlBarChart data={data.overview.performance_by_symbol} title="Performance by symbol" />
        <PnlBarChart data={data.overview.performance_by_strategy} title="Performance by strategy" />
        <PnlBarChart data={data.overview.performance_by_provider} title="Performance by provider / model source" />
      </div>

      <section className="min-w-0 rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{analyticsMode === "live" ? "Live analytics" : "Model tournament"}</div>
            <div className="mt-1 text-sm text-slate-400">
              {analyticsMode === "live"
                ? "Live Trading metrics are sourced only from live snapshots and live trades. They are not mixed with simulation accounts."
                : "Simulation and replay metrics are kept by model/account so GPT/OpenAI, DeepSeek, Gemini, and local models are not mixed together."}
            </div>
          </div>
          {analyticsMode === "simulation" ? (
            <a href={`${apiBase}/analytics/model-comparison.csv`} className="rounded-xl border border-border px-3 py-2 text-xs text-slate-200 hover:bg-white/5">
              CSV export
            </a>
          ) : null}
        </div>
        {analyticsMode === "live" ? (
          <div className="mt-4 rounded-xl border border-border bg-black/20 px-4 py-3 text-sm text-slate-300">
            Live execution is still broker-sync/manual-mirror only in this scaffold, so this panel reflects synced live snapshots and local live ledger trades rather than simulated model tournament rows.
          </div>
        ) : null}
        {analyticsMode === "simulation" ? <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr>
                <th>Scope</th>
                <th>Model</th>
                <th>Cash</th>
                <th>Reserved</th>
                <th>Available</th>
                <th>Value</th>
                <th>Return</th>
                <th>Drawdown</th>
                <th>Win</th>
                <th>Profit factor</th>
                <th>Trades</th>
                <th>Rejected</th>
                <th>Invalid</th>
                <th>Useful</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {visibleModelRows.map((row, index) => (
                <tr key={`${row.scope}:${row.provider_type}:${row.replay_run_id || row.simulation_account_id || index}`}>
                  <td>{row.scope}</td>
                  <td>
                    <div className="font-semibold text-slate-100">{row.provider_type || "manual"}</div>
                    <div className="text-[11px] text-slate-400">{row.model_name || "model unset"}</div>
                  </td>
                  <td>{formatCurrency(row.cash)}</td>
                  <td>{formatCurrency(row.reserved_cash)}</td>
                  <td>{formatCurrency(row.available_cash)}</td>
                  <td>{formatCurrency(row.portfolio_value)}</td>
                  <td>{formatPct(row.total_return)}</td>
                  <td>{formatPct(row.max_drawdown)}</td>
                  <td>{formatPct(row.win_rate)}</td>
                  <td>{row.profit_factor.toFixed(2)}</td>
                  <td>{row.trade_count}</td>
                  <td>{row.rejected_trade_count}</td>
                  <td>{row.invalid_signal_count}</td>
                  <td>{formatPct(row.useful_signal_rate)}</td>
                  <td>{row.latency_ms ? `${row.latency_ms} ms` : "-"}</td>
                </tr>
              ))}
              {!visibleModelRows.length ? (
                <tr>
                  <td colSpan={15} className="text-slate-500">No model metrics yet. Run simulation or create a replay run first.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div> : null}
      </section>
    </div>
  );
}

function resolveSimulationAccountId(accounts: SimulationAccount[], workspaceProviderType: string, selectedId: string) {
  if (selectedId && accounts.some((account) => account.id === selectedId)) return selectedId;
  return (
    accounts.find((account) => account.provider_type === workspaceProviderType)?.id ||
    accounts.find((account) => account.is_active)?.id ||
    accounts[0]?.id ||
    ""
  );
}

function MetricRow({ label, value, tone }: { label: string; value: string; tone?: "positive" | "negative" | "neutral" }) {
  const toneClass = tone === "positive" ? "text-emerald-200" : tone === "negative" ? "text-rose-200" : "text-ink";
  return (
    <div className="flex items-center justify-between rounded-xl border border-border bg-black/20 px-4 py-3">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{label}</div>
      <div className={`text-lg font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

function formatAverageLoss(averageLoss: number, averageWin: number) {
  if (averageLoss === 0 && averageWin > 0) return "No losses";
  return averageLoss;
}

function formatProfitFactor(profitFactor: number, averageLoss: number, averageWin: number) {
  if (averageLoss === 0 && averageWin > 0) return "No losses";
  return profitFactor.toFixed(2);
}
