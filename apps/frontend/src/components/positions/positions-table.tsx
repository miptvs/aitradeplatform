import type { Position } from "@/types";
import { formatCurrency, formatQuantity } from "@/lib/utils";
import { ModeBadge } from "@/components/ui/mode-badge";

export function PositionsTable({ positions }: { positions: Position[] }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-panel/90 shadow-panel">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Mode</th>
              <th>Qty</th>
              <th>Avg Entry</th>
              <th>Current</th>
              <th>Unrealized</th>
              <th>Stops</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => (
              <tr key={position.id}>
                <td>
                  <div className="font-semibold text-slate-100">{position.symbol}</div>
                  <div className="text-xs text-slate-400">{position.asset_name}</div>
                </td>
                <td><ModeBadge mode={position.mode} /></td>
                <td>{formatQuantity(position.quantity, 6)}</td>
                <td>{formatCurrency(position.avg_entry_price, position.asset_currency)}</td>
                <td>{formatCurrency(position.current_price, position.asset_currency)}</td>
                <td className={position.unrealized_pnl >= 0 ? "text-emerald-300" : "text-rose-300"}>{formatCurrency(position.unrealized_pnl, position.asset_currency)}</td>
                <td className="min-w-[12rem] text-xs text-slate-300">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-black/15 px-2.5 py-1.5">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">SL</span>
                      <span className="whitespace-nowrap font-medium text-slate-200">{position.stop_loss ? formatCurrency(position.stop_loss, position.asset_currency) : "-"}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-black/15 px-2.5 py-1.5">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">TP</span>
                      <span className="whitespace-nowrap font-medium text-slate-200">{position.take_profit ? formatCurrency(position.take_profit, position.asset_currency) : "-"}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-black/15 px-2.5 py-1.5">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">TR</span>
                      <span className="whitespace-nowrap font-medium text-slate-200">{position.trailing_stop ? formatCurrency(position.trailing_stop, position.asset_currency) : "-"}</span>
                    </div>
                  </div>
                </td>
                <td className="text-xs text-slate-300">
                  <div>{position.manual ? "Manual" : "Auto"}</div>
                  <div>{position.strategy_name || "-"}</div>
                  <div>{position.provider_type || "-"}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
