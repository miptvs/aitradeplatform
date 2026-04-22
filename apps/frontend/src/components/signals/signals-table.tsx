import type { Signal } from "@/types";
import { formatCurrency } from "@/lib/utils";
import { ModeBadge } from "@/components/ui/mode-badge";
import { StatusBadge } from "@/components/ui/status-badge";

export function SignalsTable({ signals }: { signals: Signal[] }) {
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
                <td className="uppercase text-slate-200">{signal.action}</td>
                <td>{(signal.confidence * 100).toFixed(1)}%</td>
                <td className="text-xs text-slate-300">
                  <div>{signal.strategy_name || signal.strategy_slug || "-"}</div>
                  <div>{signal.ai_rationale || "-"}</div>
                </td>
                <td className="text-xs text-slate-300">
                  <div>Entry {signal.suggested_entry ? formatCurrency(signal.suggested_entry) : "-"}</div>
                  <div>Stop {signal.suggested_stop_loss ? formatCurrency(signal.suggested_stop_loss) : "-"}</div>
                  <div>TP {signal.suggested_take_profit ? formatCurrency(signal.suggested_take_profit) : "-"}</div>
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={signal.status} />
                    <ModeBadge mode={signal.mode} />
                  </div>
                </td>
                <td className="text-xs text-slate-300">
                  <div>{signal.provider_type || "-"}</div>
                  <div>{signal.model_name || "-"}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
