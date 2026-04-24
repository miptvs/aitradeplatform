"use client";

import type { ReactNode } from "react";

import { Dialog } from "@/components/ui/dialog";
import { ModeBadge } from "@/components/ui/mode-badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatCurrency, formatPct, formatQuantity } from "@/lib/utils";
import type { Signal, SignalTrace } from "@/types";

export function SignalTraceDialog({
  open,
  signal,
  trace,
  loading,
  error,
  actions,
  onClose,
}: {
  open: boolean;
  signal: Signal | null;
  trace: SignalTrace | null;
  loading: boolean;
  error: string | null;
  actions?: ReactNode;
  onClose: () => void;
}) {
  return (
    <ProvenanceDialog
      open={open}
      signal={signal}
      trace={trace}
      loading={loading}
      error={error}
      actions={actions}
      onClose={onClose}
    />
  );
}

export function ProvenanceDialog({
  open,
  signal,
  trace,
  loading,
  error,
  actions,
  onClose,
}: {
  open: boolean;
  signal?: Signal | null;
  trace: SignalTrace | null;
  loading: boolean;
  error: string | null;
  actions?: ReactNode;
  onClose: () => void;
}) {
  const detail = trace?.signal || signal || null;
  const summary = trace?.summary || {};
  const entrypointLabel = String(trace?.entrypoint?.type || (detail ? "signal" : "object"));
  const latestEvaluation = trace?.evaluations?.[0] || null;

  return (
    <Dialog
      open={open}
      size="wide"
      title="Decision trail"
      description="One shared provenance view for signals, orders, trades, and positions. Use it to see why something exists and what happened next."
      actions={
        <div className="flex flex-wrap gap-2">
          {actions}
          <button type="button" onClick={onClose} className="rounded-xl border border-border px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
            Close
          </button>
        </div>
      }
    >
      {loading ? <div className="text-sm text-slate-400">Loading decision trail...</div> : null}
      {!loading && error ? <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{error}</div> : null}
      {!loading && !error ? (
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <TraceStat label="Opened from" value={entrypointLabel} />
            <TraceStat label="Lane" value={String(summary.mode || detail?.mode || "not routed")} />
            <TraceStat label="Execution mode" value={String(summary.execution_mode || "signal-only")} />
            <TraceStat label="Signal link" value={summary.signal_linked || detail ? "Signal-linked" : "Manual-only"} />
            <TraceStat label="Strategy" value={String(summary.strategy || detail?.strategy_name || detail?.strategy_slug || "-")} />
            <TraceStat label="Provider / model" value={`${String(summary.provider_type || detail?.provider_type || "-")} / ${String(summary.model_name || detail?.model_name || "-")}`} />
            <TraceStat label="Orders / trades" value={`${String(summary.orders_count || 0)} / ${String(summary.trades_count || 0)}`} />
            <TraceStat label="Positions" value={String(summary.positions_count || 0)} />
          </div>

          {latestEvaluation ? (
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-[0.18em] text-emerald-200">Latest review decision</div>
                  <div className="mt-2 text-sm leading-6 text-slate-200">
                    {latestEvaluation.evaluator} recorded {latestEvaluation.outcome || (latestEvaluation.approved ? "approved" : "rejected")} at{" "}
                    {latestEvaluation.created_at.slice(0, 16).replace("T", " ")}.
                  </div>
                  <div className="mt-1 text-sm text-slate-300">{latestEvaluation.reason || "No review note was stored."}</div>
                </div>
                <div className="shrink-0">
                  <StatusBadge status={latestEvaluation.outcome || (latestEvaluation.approved ? "approved" : "rejected")} />
                </div>
              </div>
            </div>
          ) : null}

          {detail ? (
            <div className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
              <section className="rounded-2xl border border-border bg-black/20 p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Origin signal</div>
                <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <TraceStat label="Symbol" value={`${detail.symbol} · ${detail.asset_name}`} />
                  <TraceStat label="Action / confidence" value={`${detail.action.toUpperCase()} · ${formatPct(detail.confidence)}`} />
                  <TraceStat label="Suggested entry" value={detail.suggested_entry ? formatCurrency(detail.suggested_entry) : "-"} />
                  <TraceStat label="Risk / reward" value={detail.estimated_risk_reward ? `${detail.estimated_risk_reward.toFixed(2)}x` : "-"} />
                </div>
                <div className="mt-4 text-sm leading-6 text-slate-200">
                  {detail.ai_rationale || "No AI rationale was stored for this signal."}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <StatusBadge status={detail.status} />
                  <span className="rounded-full border border-border px-2 py-1 text-[11px] uppercase tracking-[0.14em] text-slate-200">
                    {detail.signal_flavor}
                  </span>
                  <span className="rounded-full border border-border px-2 py-1 text-[11px] uppercase tracking-[0.14em] text-slate-300">
                    {detail.fresh_news_used ? "fresh news linked" : "generated without fresh news"}
                  </span>
                </div>
              </section>

              <section className="rounded-2xl border border-border bg-black/20 p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Lane status</div>
                <div className="mt-3 space-y-3">
                  {Object.entries(detail.lane_statuses || {}).map(([lane, laneStatus]) => (
                    <div key={lane} className="flex items-center justify-between gap-3">
                      <div className="text-sm text-slate-300">{lane === "live" ? "Live Trading" : "Simulation"}</div>
                      <StatusBadge status={laneStatus} />
                    </div>
                  ))}
                </div>
              </section>
            </div>
          ) : (
            <section className="rounded-2xl border border-border bg-black/20 p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Manual-only provenance</div>
              <div className="mt-3 text-sm leading-6 text-slate-300">
                No origin signal is linked to this object. The trail below still shows the manual ticket, risk checks, resulting position or trade impact, and audit events.
              </div>
            </section>
          )}

          <div className="grid gap-4 xl:grid-cols-2">
            <TraceList
              title="Related news"
              empty="No linked articles. The engine can still generate technical-only or AI-only signals when fresh symbol news is unavailable."
              items={(trace?.signal?.related_news || []).map((article) => (
                <div key={article.id} className="rounded-xl border border-border bg-slate-950/70 p-3">
                  <a href={article.url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-slate-100 hover:underline">
                    {article.title}
                  </a>
                  <div className="mt-1 text-xs text-slate-400">
                    {article.source} · {article.published_at.slice(0, 16).replace("T", " ")} · {article.sentiment || "unclassified"}
                  </div>
                </div>
              ))}
            />
            <TraceList
              title="Extracted events"
              empty="No extracted events were linked to this trail."
              items={(trace?.signal?.related_events || []).map((event) => (
                <div key={event.id} className="rounded-xl border border-border bg-slate-950/70 p-3">
                  <div className="text-sm font-semibold text-slate-100">{event.event_type}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {event.symbol || "market-wide"} · confidence {(event.confidence * 100).toFixed(0)}% · impact {(event.impact_score * 100).toFixed(0)}%
                  </div>
                  <div className="mt-2 text-sm text-slate-300">{event.summary}</div>
                </div>
              ))}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <TraceList
              title="Risk checks"
              empty="No persisted risk-check detail was linked to this trail."
              items={(trace?.risk_checks || []).map((check, index) => (
                <div key={`${String(check.order_id || "risk")}-${index}`} className="rounded-xl border border-border bg-slate-950/70 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-100">{String(check.rule_name || check.rule || check.name || `Risk check ${index + 1}`)}</div>
                    <StatusBadge status={truthy(check.approved ?? check.passed) ? "approved" : "blocked_by_risk"} />
                  </div>
                  <div className="mt-2 text-xs text-slate-400">Order {String(check.order_id || "-")}</div>
                  <div className="mt-2 text-sm text-slate-300">{String(check.message || check.reason || check.detail || "Risk engine recorded this check.")}</div>
                </div>
              ))}
            />
            <TraceList
              title="Stop history"
              empty="No stop-loss, take-profit, or trailing-stop history was linked yet."
              items={(trace?.stop_history || []).map((item, index) => (
                <div key={`${String(item.source || "stop")}-${index}`} className="rounded-xl border border-border bg-slate-950/70 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-100">{String(item.label || item.source || "Stop update")}</div>
                    <StatusBadge status={String(item.source || "stop")} />
                  </div>
                  <div className="mt-2 grid gap-2 text-xs text-slate-300 md:grid-cols-3">
                    <div>SL {moneyish(item.stop_loss)}</div>
                    <div>TP {moneyish(item.take_profit)}</div>
                    <div>TR {moneyish(item.trailing_stop)}</div>
                  </div>
                  {item.observed_at ? <div className="mt-2 text-xs text-slate-500">{String(item.observed_at).slice(0, 16).replace("T", " ")}</div> : null}
                </div>
              ))}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <TraceList
              title="Evaluations"
              empty="No live or simulation review steps have been recorded yet."
              items={(trace?.evaluations || []).map((evaluation) => (
                <div key={evaluation.id} className="rounded-xl border border-border bg-slate-950/70 p-3">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 break-words text-sm font-semibold text-slate-100">{evaluation.evaluator}</div>
                    <div className="shrink-0">
                      <StatusBadge status={evaluation.outcome || (evaluation.approved ? "approved" : "rejected")} />
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-slate-400">{evaluation.created_at.slice(0, 16).replace("T", " ")}</div>
                  <div className="mt-2 text-sm text-slate-300">{evaluation.reason || "No evaluation note was stored."}</div>
                </div>
              ))}
            />
            <TraceList
              title="Orders"
              empty="No order has been linked yet."
              items={(trace?.orders || []).map((order) => (
                <div key={order.id} className="rounded-xl border border-border bg-slate-950/70 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-100">Order · {order.symbol}</div>
                    <StatusBadge status={order.status} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <ModeBadge mode={order.mode} />
                    <StatusBadge status={order.manual ? "manual" : "auto"} />
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    {order.side} · {formatQuantity(order.quantity, 6)} · {formatCurrency(order.filled_price || order.requested_price || 0)}
                  </div>
                  <div className="mt-2 text-sm text-slate-300">{order.rejection_reason || order.entry_reason || order.exit_reason || "Order recorded."}</div>
                </div>
              ))}
            />
            <TraceList
              title="Positions"
              empty="No position impact has been linked yet."
              items={(trace?.positions || []).map((position) => (
                <div key={position.id} className="rounded-xl border border-border bg-slate-950/70 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-100">Position · {position.symbol}</div>
                    <StatusBadge status={position.status} />
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    {position.mode} · qty {formatQuantity(position.quantity, 6)} · entry {formatCurrency(position.avg_entry_price, position.asset_currency)}
                  </div>
                  <div className="mt-2 text-sm text-slate-300">
                    SL {moneyish(position.stop_loss)} · TP {moneyish(position.take_profit)} · TR {moneyish(position.trailing_stop)}
                  </div>
                  {position.manual_override ? <div className="mt-2 text-xs text-amber-200">Manual override active</div> : null}
                </div>
              ))}
            />
            <TraceList
              title="Trades"
              empty="No simulated or live trade has been linked yet."
              items={(trace?.trades || []).map((trade) => (
                <div key={trade.id} className="rounded-xl border border-border bg-slate-950/70 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-100">Trade · {trade.symbol}</div>
                    <ModeBadge mode={trade.mode} />
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    {trade.executed_at.slice(0, 16).replace("T", " ")} · {trade.side} · {formatQuantity(trade.quantity, 6)}
                  </div>
                  <div className="mt-2 text-sm text-slate-300">
                    Price {formatCurrency(trade.price)} · Realized {formatCurrency(trade.realized_pnl)}
                  </div>
                </div>
              ))}
            />
          </div>

          <TraceList
            title="Audit trail"
            empty="No audit entries were linked to this decision chain yet."
            items={(trace?.audit_logs || []).slice(0, 12).map((item) => (
              <div key={item.id} className="rounded-xl border border-border bg-slate-950/70 p-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 break-words text-sm font-semibold text-slate-100">{item.action}</div>
                  <div className="shrink-0">
                    <StatusBadge status={item.status} />
                  </div>
                </div>
                <div className="mt-2 text-xs text-slate-400">
                  {item.occurred_at.slice(0, 16).replace("T", " ")} · {item.mode || "system"} · {item.target_type}
                </div>
              </div>
            ))}
          />
        </div>
      ) : null}
    </Dialog>
  );
}

function TraceStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-2xl border border-border bg-black/20 p-3">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-2 break-words text-sm text-slate-100">{value}</div>
    </div>
  );
}

function TraceList({ title, empty, items }: { title: string; empty: string; items: ReactNode[] }) {
  return (
    <section className="min-w-0 rounded-2xl border border-border bg-black/20 p-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-400">{title}</div>
      <div className="mt-3 space-y-3">{items.length ? items : <div className="text-sm text-slate-400">{empty}</div>}</div>
    </section>
  );
}

function truthy(value: unknown) {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return ["true", "ok", "passed", "approved"].includes(value.toLowerCase());
  return Boolean(value);
}

function moneyish(value: unknown) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "-";
  return formatCurrency(numeric);
}
