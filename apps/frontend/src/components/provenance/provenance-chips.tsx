"use client";

import { ModeBadge } from "@/components/ui/mode-badge";
import { StatusBadge } from "@/components/ui/status-badge";
import type { Order, Position, Trade } from "@/types";

type TraceableRow = Order | Trade | Position;

export function ProvenanceChips({ item }: { item: TraceableRow }) {
  const manual = "manual" in item ? item.manual : true;
  const hasSignal = "signal_id" in item ? Boolean(item.signal_id) : Boolean(item.provider_type || item.model_name || (!manual && item.strategy_name));
  const status = "status" in item ? item.status : "executed";
  const blocked = "rejection_reason" in item && Boolean(item.rejection_reason);

  return (
    <div className="flex flex-wrap gap-1.5">
      <ModeBadge mode={item.mode} />
      <MiniChip label={manual ? "Manual" : "Auto"} tone={manual ? "neutral" : "accent"} />
      <MiniChip label={hasSignal ? "Signal-linked" : "Manual-only"} tone={hasSignal ? "accent" : "neutral"} />
      {blocked ? <MiniChip label="Risk blocked" tone="danger" /> : <StatusBadge status={status} />}
    </div>
  );
}

export function TraceButton({ onClick, label = "View trace" }: { onClick: () => void; label?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border border-border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-200 hover:bg-white/5"
      title="Open the full decision trail for this row."
    >
      {label}
    </button>
  );
}

function MiniChip({ label, tone }: { label: string; tone: "neutral" | "accent" | "danger" }) {
  const className =
    tone === "accent"
      ? "border-cyan-500/30 bg-cyan-500/15 text-cyan-200"
      : tone === "danger"
        ? "border-rose-500/30 bg-rose-500/15 text-rose-200"
        : "border-slate-500/30 bg-slate-500/15 text-slate-200";

  return <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${className}`}>{label}</span>;
}
