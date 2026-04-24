import { Eye, Flag, PencilLine, Shield, XCircle } from "lucide-react";

import { ProvenanceChips, TraceButton } from "@/components/provenance/provenance-chips";
import { ActionMenu, ActionMenuButton } from "@/components/ui/action-menu";
import { formatCurrency, formatQuantity } from "@/lib/utils";
import type { Position } from "@/types";

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
  if (!positions.length) {
    return <div className="rounded-2xl border border-border bg-panel/90 p-5 text-sm text-slate-400 shadow-panel">{emptyMessage}</div>;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-panel/90 shadow-panel">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Mode</th>
              <th>Size</th>
              <th>Entry / Mark</th>
              <th>PnL</th>
              <th>Stops</th>
              <th>Source</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => {
              const hasStops = Boolean(position.stop_loss || position.take_profit || position.trailing_stop);
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
                        label="SL"
                        title="Automatically closes the trade if price moves against you to this level."
                        value={position.stop_loss ? formatCurrency(position.stop_loss, position.asset_currency) : "-"}
                      />
                      <StopValue
                        label="TP"
                        title="Automatically closes the trade once the target profit price is reached."
                        value={position.take_profit ? formatCurrency(position.take_profit, position.asset_currency) : "-"}
                      />
                      <StopValue
                        label="TR"
                        title="Moves the stop as price rises, helping protect profits."
                        value={position.trailing_stop ? formatCurrency(position.trailing_stop, position.asset_currency) : "-"}
                      />
                      <div className="pt-1">
                        {hasStops ? <MiniBadge tone="success" label="Stops active" /> : <MiniBadge tone="neutral" label="No stops" />}
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
    <div title={title} className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-black/15 px-2.5 py-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</span>
      <span className="whitespace-nowrap font-medium text-slate-200">{value}</span>
    </div>
  );
}
