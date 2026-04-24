"use client";

import { useMemo, useState } from "react";

import { ProvenanceChips, TraceButton } from "@/components/provenance/provenance-chips";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatCurrency } from "@/lib/utils";
import type { Order, Trade } from "@/types";

type SortMode = "newest" | "oldest" | "symbol" | "largest";

export function TradesTable({
  trades,
  orders,
  onViewTrace,
}: {
  trades?: Trade[];
  orders?: Order[];
  onViewTrace?: (type: "order" | "trade", item: Order | Trade) => void;
}) {
  const rows = useMemo(() => [...(trades || orders || [])], [orders, trades]);
  const [sortMode, setSortMode] = useState<SortMode>("newest");

  const sortedRows = useMemo(() => {
    const next = [...rows];
    next.sort((left, right) => compareRows(left, right, sortMode));
    return next;
  }, [rows, sortMode]);

  if (!sortedRows.length) {
    return (
      <div className="rounded-2xl border border-border bg-panel/90 p-4 text-sm text-slate-400 shadow-panel">
        No order or trade history available yet.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-panel/90 shadow-panel">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Blotter</div>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <span>Sort</span>
          <select
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value as SortMode)}
            className="rounded-lg border border-border bg-slate-950 px-2 py-1 text-xs text-slate-200"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="symbol">Symbol A-Z</option>
            <option value="largest">Largest notional</option>
          </select>
        </label>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <th>Time</th>
              <th>Symbol</th>
              <th>Provenance</th>
              <th>Side</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Fees</th>
              {"status" in sortedRows[0] ? <th>Status</th> : <th>Realized</th>}
              <th>Strategy</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row: Trade | Order) => (
              <tr key={row.id}>
                <td>{rowTime(row).slice(0, 16).replace("T", " ")}</td>
                <td>
                  <div className="font-semibold text-slate-100">{row.symbol}</div>
                  <div className="text-xs text-slate-400">{row.asset_name}</div>
                  {onViewTrace ? (
                    <div className="mt-2">
                      <TraceButton label="Trace" onClick={() => onViewTrace("status" in row ? "order" : "trade", row)} />
                    </div>
                  ) : null}
                </td>
                <td>
                  <ProvenanceChips item={row} />
                </td>
                <td className="uppercase">{row.side}</td>
                <td>{row.quantity}</td>
                <td>{formatCurrency(rowPrice(row))}</td>
                <td>{formatCurrency(row.fees)}</td>
                <td>
                  {"status" in row ? (
                    <StatusBadge status={row.status} />
                  ) : (
                    <span className={row.realized_pnl >= 0 ? "text-emerald-300" : "text-rose-300"}>{formatCurrency(row.realized_pnl)}</span>
                  )}
                </td>
                <td className="text-xs text-slate-300">
                  <div>{row.strategy_name || "-"}</div>
                  <div>{row.provider_type || "-"}</div>
                </td>
                <td className="max-w-[260px] text-xs text-slate-300">
                  {"status" in row ? row.rejection_reason || row.entry_reason || row.exit_reason || "-" : row.entry_reason || row.exit_reason || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function rowTime(row: Trade | Order) {
  return "created_at" in row ? row.executed_at || row.created_at : row.executed_at;
}

function rowPrice(row: Trade | Order) {
  return "price" in row ? row.price : row.filled_price || row.requested_price || 0;
}

function rowNotional(row: Trade | Order) {
  return Math.abs((row.quantity || 0) * rowPrice(row));
}

function compareRows(left: Trade | Order, right: Trade | Order, sortMode: SortMode) {
  if (sortMode === "oldest") {
    return rowTime(left).localeCompare(rowTime(right));
  }
  if (sortMode === "symbol") {
    return left.symbol.localeCompare(right.symbol);
  }
  if (sortMode === "largest") {
    return rowNotional(right) - rowNotional(left);
  }
  return rowTime(right).localeCompare(rowTime(left));
}
