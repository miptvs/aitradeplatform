import { cn } from "@/lib/utils";

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const tone =
    normalized === "ok" ||
    normalized === "filled" ||
    normalized === "approved" ||
    normalized === "connected" ||
    normalized === "enabled" ||
    normalized === "executed" ||
    normalized === "open" ||
    normalized === "simulation" ||
    normalized === "sim" ||
    normalized === "simulated" ||
    normalized === "executed_live"
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
      : normalized === "candidate" ||
          normalized === "shared" ||
          normalized === "inherited" ||
          normalized === "manual" ||
          normalized === "auto" ||
          normalized === "signal_suggestion" ||
          normalized === "order_ticket" ||
          normalized === "current_position"
        ? "bg-cyan-500/15 text-cyan-200 border-cyan-500/30"
      : normalized === "warning" ||
          normalized === "warn" ||
          normalized === "pending" ||
          normalized === "scaffolded" ||
          normalized === "disabled" ||
          normalized === "guarded" ||
          normalized === "live" ||
          normalized === "custom" ||
          normalized === "override" ||
          normalized === "manual_override" ||
          normalized === "manual_edit" ||
          normalized === "closed" ||
          normalized === "blocked_by_risk" ||
          normalized === "sent_to_live_workflow"
        ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
        : "bg-rose-500/15 text-rose-300 border-rose-500/30";

  return <span className={cn("rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]", tone)}>{status}</span>;
}
