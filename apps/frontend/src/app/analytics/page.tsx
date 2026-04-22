"use client";

import { EquityCurveChart } from "@/components/charts/equity-curve-chart";
import { PnlBarChart } from "@/components/charts/pnl-bar-chart";
import { StatsCard } from "@/components/stats-card";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";

export default function AnalyticsPage() {
  const { data, loading, error } = useApi(async () => {
    const [overview, combinedCurve, simVsLive] = await Promise.all([
      api.getAnalyticsOverview(),
      api.getEquityCurve(),
      api.getSimulationVsLive()
    ]);
    return { overview, combinedCurve, simVsLive };
  });

  if (loading || !data) return <div className="text-sm text-slate-400">Loading analytics...</div>;
  if (error) return <div className="text-sm text-rose-300">Analytics failed to load: {error}</div>;

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
    </div>
  );
}
