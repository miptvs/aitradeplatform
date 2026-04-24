import type { ReactNode } from "react";

import type { Signal } from "@/types";
import { formatCurrency } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/status-badge";

export function SignalsTable({
  signals,
  onSelectSignal,
  renderActions,
}: {
  signals: Signal[];
  onSelectSignal?: (signal: Signal) => void;
  renderActions?: (signal: Signal) => ReactNode;
}) {
  const showActions = Boolean(onSelectSignal || renderActions);

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-panel/90 shadow-panel">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <th>Time</th>
              <th>Symbol</th>
              <th>Action</th>
              <th>Confidence</th>
              <th>Strategy</th>
              <th>Entry / Risk</th>
              <th>Status</th>
              <th>Provider</th>
              {showActions ? <th>Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {signals.map((signal) => (
              <tr key={signal.id}>
                <td>{signal.occurred_at.slice(0, 16).replace("T", " ")}</td>
                <td>
                  <div className="font-semibold text-slate-100">{signal.symbol}</div>
                  <div className="text-xs text-slate-400">{signal.asset_name}</div>
                </td>
                <td className="text-slate-200">
                  <div className="font-semibold uppercase">{signalActionLabel(signal)}</div>
                  {signal.action === "sell" ? (
                    <div className="mt-1 text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      {signalIntentLabel(signal)}
                    </div>
                  ) : null}
                </td>
                <td>{(signal.confidence * 100).toFixed(1)}%</td>
                <td className="min-w-[14rem] text-xs">
                  <div className="font-semibold text-slate-100">{signal.strategy_name || signal.strategy_slug || "-"}</div>
                  <div className="mt-1 text-[11px] leading-5 text-slate-400" title={signal.ai_rationale || undefined}>
                    {truncateText(signal.ai_rationale || "No AI rationale recorded yet.", 140)}
                  </div>
                </td>
                <td className="text-xs text-slate-300">
                  <div>Entry {signal.suggested_entry ? formatCurrency(signal.suggested_entry) : "-"}</div>
                  <div>Stop {signal.suggested_stop_loss ? formatCurrency(signal.suggested_stop_loss) : "-"}</div>
                  <div>TP {signal.suggested_take_profit ? formatCurrency(signal.suggested_take_profit) : "-"}</div>
                </td>
                <td>
                  <StatusBadge status={signal.status} />
                </td>
                <td className="text-xs text-slate-300">
                  <div>{signal.provider_type || "-"}</div>
                  <div>{signal.model_name || "-"}</div>
                </td>
                {showActions ? (
                  <td className="text-right">
                    <div className="flex flex-wrap justify-end gap-2">
                      {onSelectSignal ? (
                        <button
                          type="button"
                          onClick={() => onSelectSignal(signal)}
                          className="rounded-full border border-border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-200 hover:bg-white/5"
                        >
                          View trace
                        </button>
                      ) : null}
                      {renderActions ? renderActions(signal) : null}
                    </div>
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function truncateText(value: string, maxLength: number) {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 1)}…`;
}

function signalActionLabel(signal: Signal) {
  if (signal.action === "sell") {
    return signal.metadata_json?.trade_intent === "close_long" ? "Close / Sell" : "Sell";
  }
  if (signal.action === "buy") {
    return signal.metadata_json?.trade_intent === "open_long" ? "Open / Buy" : "Buy";
  }
  return signal.action;
}

function signalIntentLabel(signal: Signal) {
  if (signal.metadata_json?.trade_intent === "close_long") return "Exit held position";
  return "Directional sell signal";
}
