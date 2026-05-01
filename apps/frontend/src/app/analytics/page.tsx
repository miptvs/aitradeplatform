"use client";

import { EquityCurveChart } from "@/components/charts/equity-curve-chart";
import { PnlBarChart } from "@/components/charts/pnl-bar-chart";
import { StatsCard } from "@/components/stats-card";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatCurrency, formatPct } from "@/lib/utils";

export default function AnalyticsPage() {
  const { data, loading, error } = useApi(async () => {
    const [overview, combinedCurve, simVsLive, modelComparison] = await Promise.all([
      api.getAnalyticsOverview(),
      api.getEquityCurve(),
      api.getSimulationVsLive(),
      api.getModelComparison()
    ]);
    return { overview, combinedCurve, simVsLive, modelComparison };
  });

  if (loading || !data) return <div className="text-sm text-slate-400">Loading analytics...</div>;
  if (error) return <div className="text-sm text-rose-300">Analytics failed to load: {error}</div>;
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

  return (
    <div className="space-y-6">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Analytics</div>
        <h1 className="mt-1 text-2xl font-semibold text-slate-100">Performance, risk, and attribution</h1>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatsCard label="Total return" value={data.overview.total_return} kind="percent" />
        <StatsCard label="Sharpe" value={data.overview.sharpe} kind="number" />
        <StatsCard label="Sortino" value={data.overview.sortino} kind="number" />
        <StatsCard label="Max drawdown" value={data.overview.max_drawdown} kind="percent" />
        <StatsCard label="Average win" value={data.overview.average_win} />
        <StatsCard label="Average loss" value={data.overview.average_loss} />
        <StatsCard label="Profit factor" value={data.overview.profit_factor} kind="number" />
        <StatsCard label="Confidence correlation" value={data.overview.confidence_correlation} kind="number" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <EquityCurveChart data={data.combinedCurve} title="Portfolio equity curve" />
        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Simulation vs Live</div>
          <div className="mt-4 grid gap-3">
            <StatsCard label="Live return" value={data.simVsLive.live_return} kind="percent" />
            <StatsCard label="Simulation return" value={data.simVsLive.simulation_return} kind="percent" />
            <StatsCard label="Delta" value={data.simVsLive.delta_return} kind="percent" />
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <PnlBarChart data={data.overview.performance_by_symbol} title="Performance by symbol" />
        <PnlBarChart data={data.overview.performance_by_strategy} title="Performance by strategy" />
        <PnlBarChart data={data.overview.performance_by_provider} title="Performance by provider / model source" />
      </div>

      <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Model tournament</div>
            <div className="mt-1 text-sm text-slate-400">
              Simulation and replay metrics are kept by model/account so GPT/OpenAI, DeepSeek, Gemini, and local models are not mixed together.
            </div>
          </div>
          <a href={`${apiBase}/analytics/model-comparison.csv`} className="rounded-xl border border-border px-3 py-2 text-xs text-slate-200 hover:bg-white/5">
            CSV export
          </a>
        </div>
        <div className="mt-4 overflow-x-auto">
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
              {data.modelComparison.map((row, index) => (
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
              {!data.modelComparison.length ? (
                <tr>
                  <td colSpan={15} className="text-slate-500">No model metrics yet. Run simulation or create a replay run first.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
