import { cn } from "@/lib/utils";

export function ModeBadge({ mode }: { mode: string }) {
  const tone =
    mode === "simulation"
      ? "bg-cyan-500/15 text-cyan-200 border-cyan-500/30"
      : mode === "live"
        ? "bg-rose-500/15 text-rose-200 border-rose-500/30"
        : "bg-slate-500/15 text-slate-200 border-slate-500/30";

  return <span className={cn("rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]", tone)}>{mode}</span>;
}
