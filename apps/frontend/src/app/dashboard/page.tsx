"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";

import { EquityCurveChart } from "@/components/charts/equity-curve-chart";
import { ExposureChart } from "@/components/charts/exposure-chart";
import { RecentActivity } from "@/components/recent-activity";
import { SignalsTable } from "@/components/signals/signals-table";
import { StatsCard } from "@/components/stats-card";
import { TradesTable } from "@/components/trades/trades-table";
import { RiskBanner } from "@/components/ui/risk-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatCurrency, formatDateTime } from "@/lib/utils";
import { useWorkspace } from "@/components/layout/workspace-provider";

export default function DashboardPage() {
  const workspace = useWorkspace();
  const [mode, setMode] = useState<"simulation" | "live" | "combined">("simulation");
  const [latestTradesOpen, setLatestTradesOpen] = useState(true);
  const [latestSignalsOpen, setLatestSignalsOpen] = useState(true);
  const { data, loading, error, reload } = useApi(async () => {
    const [summary, snapshots, positions, orders, trades, signals, alerts, health] = await Promise.all([
      api.getPortfolioSummary(mode === "combined" ? undefined : mode),
      api.getPortfolioSnapshots(),
      api.getPositions(),
      api.getOrders(),
      api.getTrades(),
      api.getSignals(workspace.signalProviderType),
      api.getAlerts(),
      api.getHealth()
    ]);
    return { summary, snapshots, positions, orders, trades, signals, alerts, health };
  }, [mode, workspace.signalProviderType]);

  const chartData = useMemo(() => buildDashboardCurve(data?.snapshots ?? [], mode), [data?.snapshots, mode]);

  if (loading || !data) return <div className="text-sm text-slate-400">Loading dashboard...</div>;
  if (error) return <div className="text-sm text-rose-300">Dashboard failed to load: {error}</div>;

  const filteredPositions = data.positions.filter((position) => mode === "combined" || position.mode === mode);
  const filteredOrders = data.orders.filter((order) => mode === "combined" || order.mode === mode);
  const filteredTrades = data.trades.filter((trade) => mode === "combined" || trade.mode === mode);

  const filteredSignals = data.signals.filter(
    (signal) => mode === "combined" || signal.mode === "both" || signal.mode === mode
  );

  const exposureData = filteredPositions.slice(0, 6).map((position) => ({
    name: position.symbol,
    value: position.current_price * position.quantity
  }));

  const modeLabel = mode === "combined" ? "Combined" : mode === "live" ? "Live" : "Simulation";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Dashboard</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100">{modeLabel} portfolio command center</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(["simulation", "live", "combined"] as const).map((option) => (
            <button
              key={option}
              onClick={() => setMode(option)}
              className={`rounded-full border px-4 py-2 text-xs uppercase tracking-[0.18em] ${mode === option ? "" : "border-border text-slate-300 hover:bg-white/5"}`}
              style={
                mode === option
                  ? {
                      borderColor: workspace.theme.accentBorder,
                      backgroundColor: workspace.theme.accentSurface,
                      color: workspace.theme.primary,
                    }
                  : undefined
              }
            >
              {option}
            </button>
          ))}
          <button onClick={reload} className="rounded-xl border border-border px-4 py-2 text-sm text-slate-200 hover:bg-white/5">
            Refresh
          </button>
        </div>
      </div>

      <RiskBanner alerts={data.alerts} />

      <div className="rounded-xl border border-border bg-panel/90 px-4 py-3 text-sm text-slate-300 shadow-panel">
        Viewing <span className="font-semibold text-slate-100">{modeLabel}</span>. The earlier confusing numbers came from the dashboard blending seeded live and simulation ledgers together.
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatsCard label="Total Portfolio Value" value={data.summary.total_portfolio_value} />
        <StatsCard label="Cash Available" value={data.summary.cash_available} />
        <StatsCard label="Realized PnL" value={data.summary.realized_pnl} />
        <StatsCard label="Unrealized PnL" value={data.summary.unrealized_pnl} />
        <StatsCard label="Daily Return" value={data.summary.daily_return} kind="percent" />
        <StatsCard label="Weekly Return" value={data.summary.weekly_return} kind="percent" />
        <StatsCard label="Monthly Return" value={data.summary.monthly_return} kind="percent" />
        <StatsCard label="Win Rate" value={data.summary.win_rate} kind="percent" detail={`${data.summary.closed_trades_count} closed sells`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <EquityCurveChart data={chartData} title={`${modeLabel} Equity Curve`} />
        <div className="space-y-4">
          <ExposureChart data={exposureData} />
          <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">System Status</div>
            <div className="mt-4 space-y-3">
              <div className="rounded-xl border border-border bg-black/20 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Best / Worst</div>
                <div className="mt-2 flex items-center justify-between text-sm">
                  <span className="text-slate-200">{data.summary.best_performer.symbol}</span>
                  <span className="text-emerald-300">{formatCurrency(data.summary.best_performer.pnl)}</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-sm">
                  <span className="text-slate-200">{data.summary.worst_performer.symbol}</span>
                  <span className="text-rose-300">{formatCurrency(data.summary.worst_performer.pnl)}</span>
                </div>
              </div>
              <div className="rounded-xl border border-border bg-black/20 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Providers</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {data.health.providers.map((provider) => (
                    <div key={provider.provider_type} className="flex items-center gap-2">
                      <span className="text-xs text-slate-300">{provider.provider_type}</span>
                      <StatusBadge status={provider.status} />
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-black/20 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Operational warnings</div>
                <div className="mt-2 space-y-2">
                  {data.health.warnings?.length ? (
                    data.health.warnings.slice(0, 5).map((warning) => (
                      <div key={warning} className="text-sm text-amber-200">{warning}</div>
                    ))
                  ) : (
                    <div className="text-sm text-emerald-200">No current blocking warnings.</div>
                  )}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-black/20 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Freshness</div>
                <div className="mt-2 space-y-1 text-sm text-slate-300">
                  <div>News: {formatDateTime(data.health.freshness?.news_latest_published_at, { fallback: "Not recorded" })}</div>
                  <div>Market: {formatDateTime(data.health.freshness?.market_latest_snapshot_at, { fallback: "Not recorded" })}</div>
                  <div>Signals: {formatDateTime(data.health.freshness?.last_signal_generation_at, { fallback: "Not recorded" })}</div>
                  <div>Scheduler: {data.health.freshness?.scheduler_status || "unknown"}</div>
                </div>
              </div>
              <div className="rounded-xl border border-border bg-black/20 p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Broker Sync</div>
                <div className="mt-2 space-y-2">
                  {data.health.broker_sync?.map((account) => (
                    <div key={String(account.account_id)} className="flex items-center justify-between gap-3">
                      <span className="text-sm text-slate-200">{String(account.name)}</span>
                      <StatusBadge status={String(account.last_sync_status || account.status || "disconnected")} />
                    </div>
                  ))}
                  {!data.health.broker_sync?.length ? (
                    <div className="text-sm text-slate-500">Trading212 not connected.</div>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <RecentActivity orders={filteredOrders} trades={filteredTrades} signals={filteredSignals} />
        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Risk / Automation Snapshot</div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-border bg-black/20 p-3">
              <div className="text-xs text-slate-400">Open positions</div>
              <div className="mt-1 text-lg font-semibold text-slate-100">{data.summary.open_positions_count}</div>
            </div>
            <div className="rounded-xl border border-border bg-black/20 p-3">
              <div className="text-xs text-slate-400">Exposure</div>
              <div className="mt-1 text-lg font-semibold text-slate-100">
                {formatCurrency(Number(data.summary.risk_exposure_summary.gross_exposure || 0))}
              </div>
            </div>
            <div className="rounded-xl border border-border bg-black/20 p-3">
              <div className="text-xs text-slate-400">Automation</div>
              <div className="mt-1 text-sm text-slate-100">{data.summary.automation_status.safety}</div>
            </div>
            <div className="rounded-xl border border-border bg-black/20 p-3">
              <div className="text-xs text-slate-400">Latest health event</div>
              <div className="mt-1 text-sm text-slate-100">{data.health.events[0]?.message || "No health events yet"}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <DashboardDropdown
          title="Latest Trades"
          description="Most recent executions for the selected dashboard lane."
          count={filteredTrades.length}
          open={latestTradesOpen}
          onToggle={() => setLatestTradesOpen((current) => !current)}
        >
          <TradesTable trades={filteredTrades.slice(0, 10)} />
        </DashboardDropdown>

        <DashboardDropdown
          title="Latest Signals"
          description="Newest shared signal candidates for this workspace provider."
          count={filteredSignals.length}
          open={latestSignalsOpen}
          onToggle={() => setLatestSignalsOpen((current) => !current)}
        >
          <SignalsTable signals={filteredSignals.slice(0, 8)} />
        </DashboardDropdown>
      </div>
    </div>
  );
}

function DashboardDropdown({
  title,
  description,
  count,
  open,
  onToggle,
  children,
}: {
  title: string;
  description: string;
  count: number;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full flex-col gap-3 text-left md:flex-row md:items-center md:justify-between"
        aria-expanded={open}
      >
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{title}</div>
          <div className="mt-1 text-sm text-slate-400">{description}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-border px-3 py-1 text-xs text-slate-300">{count} total</span>
          <span className="rounded-full border border-border px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-200">
            {open ? "Close" : "Open"}
          </span>
        </div>
      </button>
      {open ? <div className="mt-4">{children}</div> : null}
    </section>
  );
}

function buildDashboardCurve(
  snapshots: Array<{ mode: string; timestamp: string; total_value: number }>,
  mode: "simulation" | "live" | "combined"
) {
  const selected = mode === "combined" ? snapshots : snapshots.filter((snapshot) => snapshot.mode === mode);
  const perDayMode = new Map<string, { timestamp: string; total_value: number; mode: string }>();

  for (const snapshot of selected) {
    const day = snapshot.timestamp.slice(0, 10);
    const key = mode === "combined" ? `${day}:${snapshot.mode}` : day;
    const existing = perDayMode.get(key);
    if (!existing || snapshot.timestamp > existing.timestamp) {
      perDayMode.set(key, snapshot);
    }
  }

  const daily = new Map<string, number>();
  for (const snapshot of perDayMode.values()) {
    const day = snapshot.timestamp.slice(0, 10);
    daily.set(day, (daily.get(day) || 0) + snapshot.total_value);
  }

  return Array.from(daily.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([day, value]) => ({ timestamp: day, value }));
}
