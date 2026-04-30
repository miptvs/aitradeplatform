import { useMemo, useState } from "react";
import { Eye, Flag, PencilLine, Shield, XCircle } from "lucide-react";

import { ProvenanceChips, TraceButton } from "@/components/provenance/provenance-chips";
import { ActionMenu, ActionMenuButton } from "@/components/ui/action-menu";
import { formatCurrency, formatQuantity } from "@/lib/utils";
import type { Position } from "@/types";

type SortKey = "symbol" | "mode" | "size" | "entry" | "pnl" | "stops" | "source";
type SortDirection = "asc" | "desc";

export function PositionManagementTable({
  positions,
  emptyMessage,
  onViewDetails,
  onEditStops,
  onClose,
  onMarkOverride,
  onViewTrace,
}: {
  positions: Position[];
  emptyMessage: string;
  onViewDetails: (position: Position) => void;
  onEditStops: (position: Position) => void;
  onClose: (position: Position) => void;
  onMarkOverride: (position: Position) => void;
  onViewTrace?: (position: Position) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("symbol");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const sortedPositions = useMemo(() => {
    return [...positions].sort((left, right) => {
      const leftValue = sortValue(left, sortKey);
      const rightValue = sortValue(right, sortKey);
      const comparison =
        typeof leftValue === "number" && typeof rightValue === "number"
          ? leftValue - rightValue
          : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: "base" });
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [positions, sortDirection, sortKey]);

  function changeSort(nextKey: SortKey) {
    if (nextKey === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection("asc");
  }

  if (!positions.length) {
    return <div className="rounded-2xl border border-border bg-panel/90 p-5 text-sm text-slate-400 shadow-panel">{emptyMessage}</div>;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-panel/90 shadow-panel">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <SortableHeader label="Symbol" sortKey="symbol" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <SortableHeader label="Mode" sortKey="mode" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <SortableHeader label="Size" sortKey="size" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <SortableHeader label="Entry / Mark" sortKey="entry" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <SortableHeader label="PnL" sortKey="pnl" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <SortableHeader label="Stops" sortKey="stops" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <SortableHeader label="Source" sortKey="source" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedPositions.map((position) => {
              const hasStops = Boolean(position.stop_loss || position.take_profit || position.trailing_stop);
              const isOpen = position.status === "open";
              return (
                <tr key={position.id}>
                  <td>
                    <div className="font-semibold text-slate-100">{position.symbol}</div>
                    <div className="text-xs text-slate-400">{position.asset_name}</div>
                    {onViewTrace ? (
                      <div className="mt-2">
                        <TraceButton label="Trace" onClick={() => onViewTrace(position)} />
                      </div>
                    ) : null}
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-2">
                      <ProvenanceChips item={position} />
                      {position.manual_override ? <MiniBadge tone="warning" label="Override" /> : null}
                    </div>
                  </td>
                  <td>
                    <div>{formatQuantity(position.quantity, 6)}</div>
                    <div className="text-xs text-slate-500">{position.asset_currency || "USD"}</div>
                  </td>
                  <td className="text-sm text-slate-200">
                    <div>{formatCurrency(position.avg_entry_price, position.asset_currency)}</div>
                    <div className="text-xs text-slate-400">{formatCurrency(position.current_price, position.asset_currency)}</div>
                  </td>
                  <td className={position.unrealized_pnl >= 0 ? "text-emerald-300" : "text-rose-300"}>
                    <div>{formatCurrency(position.unrealized_pnl, position.asset_currency)}</div>
                    <div className="text-xs text-slate-400">Realized {formatCurrency(position.realized_pnl, position.asset_currency)}</div>
                  </td>
                  <td className="min-w-[12rem] text-xs text-slate-300">
                    <div className="space-y-1.5">
                      <StopValue
                        label="Stop loss"
                        title="Automatically closes the trade if price moves against you to this level."
                        value={position.stop_loss ? formatCurrency(position.stop_loss, position.asset_currency) : "-"}
                      />
                      <StopValue
                        label="Take profit"
                        title="Automatically closes the trade once the target profit price is reached."
                        value={position.take_profit ? formatCurrency(position.take_profit, position.asset_currency) : "-"}
                      />
                      <StopValue
                        label="Trailing"
                        title="Moves the stop as price rises, helping protect profits."
                        value={position.trailing_stop ? formatCurrency(position.trailing_stop, position.asset_currency) : "-"}
                      />
                      <div className="pt-1">
                        {isOpen && hasStops ? <MiniBadge tone="success" label="Stops active" /> : <MiniBadge tone="neutral" label={isOpen ? "No stops" : "Closed"} />}
                      </div>
                    </div>
                  </td>
                  <td className="text-xs text-slate-300">
                    <div>{position.strategy_name || "-"}</div>
                    <div>{position.provider_type || "Manual workflow"}</div>
                    <div>{position.model_name || "-"}</div>
                  </td>
                  <td className="text-right">
                    <ActionMenu>
                      {onViewTrace ? (
                        <ActionMenuButton title="Open the full decision trail: origin signal, risk checks, orders, trades, stops, and audit events." onClick={() => onViewTrace(position)}>
                          <span className="flex items-center gap-2"><Shield size={14} /> View trace</span>
                        </ActionMenuButton>
                      ) : null}
                      <ActionMenuButton title="Inspect the full position metadata and notes." onClick={() => onViewDetails(position)}>
                        <span className="flex items-center gap-2"><Eye size={14} /> View details</span>
                      </ActionMenuButton>
                      {isOpen ? (
                        <>
                          <ActionMenuButton title="Adjust stop loss, take profit, and trailing stop in one compact modal." onClick={() => onEditStops(position)}>
                            <span className="flex items-center gap-2"><PencilLine size={14} /> Edit stops</span>
                          </ActionMenuButton>
                          <ActionMenuButton title="Close part of the position by percentage, or leave blank in the modal to close the full line." onClick={() => onClose(position)}>
                            <span className="flex items-center gap-2"><XCircle size={14} /> Close partial / full</span>
                          </ActionMenuButton>
                          <ActionMenuButton title="Marks this line as a manual override so future automation decisions can treat it carefully." onClick={() => onMarkOverride(position)}>
                            <span className="flex items-center gap-2"><Flag size={14} /> Mark manual override</span>
                          </ActionMenuButton>
                          <ActionMenuButton title="Use this if the position should now be treated as actively managed by risk controls." onClick={() => onEditStops(position)}>
                            <span className="flex items-center gap-2"><Shield size={14} /> Convert to managed</span>
                          </ActionMenuButton>
                        </>
                      ) : null}
                    </ActionMenu>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SortableHeader({
  label,
  sortKey,
  activeKey,
  direction,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  direction: SortDirection;
  onSort: (key: SortKey) => void;
}) {
  const active = sortKey === activeKey;
  return (
    <th>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`inline-flex items-center gap-1 rounded-lg px-1.5 py-1 text-left hover:bg-white/5 ${
          active ? "text-cyan-100" : "text-slate-400"
        }`}
        title={`Sort positions by ${label.toLowerCase()}.`}
      >
        <span>{label}</span>
        <span className="text-[10px]">{active ? (direction === "asc" ? "▲" : "▼") : "↕"}</span>
      </button>
    </th>
  );
}

function sortValue(position: Position, key: SortKey) {
  if (key === "symbol") return `${position.symbol} ${position.asset_name}`;
  if (key === "mode") return `${position.mode} ${position.manual ? "manual" : "auto"} ${position.status}`;
  if (key === "size") return Math.abs(position.quantity || 0);
  if (key === "entry") return position.avg_entry_price || 0;
  if (key === "pnl") return (position.unrealized_pnl || 0) + (position.realized_pnl || 0);
  if (key === "stops") {
    return [position.stop_loss, position.take_profit, position.trailing_stop].filter((value) => value !== null && value !== undefined).length;
  }
  return `${position.strategy_name || ""} ${position.provider_type || ""} ${position.model_name || ""}`;
}

function MiniBadge({ label, tone }: { label: string; tone: "neutral" | "accent" | "warning" | "success" }) {
  const className =
    tone === "accent"
      ? "border-cyan-500/30 bg-cyan-500/15 text-cyan-200"
      : tone === "warning"
        ? "border-amber-500/30 bg-amber-500/15 text-amber-200"
        : tone === "success"
          ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-200"
          : "border-slate-500/30 bg-slate-500/15 text-slate-200";
  return <span className={`inline-flex whitespace-nowrap rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${className}`}>{label}</span>;
}

function StopValue({ label, value, title }: { label: string; value: string; title: string }) {
  return (
    <div title={title} className="grid grid-cols-[6.5rem_1fr] items-center gap-2 rounded-xl border border-border/70 bg-black/15 px-2.5 py-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</span>
      <span className="whitespace-nowrap font-medium text-slate-200">{value}</span>
    </div>
  );
}
