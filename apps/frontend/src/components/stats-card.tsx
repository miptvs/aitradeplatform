import { formatCurrency, formatPct } from "@/lib/utils";

export function StatsCard({
  label,
  value,
  kind = "currency",
  detail
}: {
  label: string;
  value: number | string;
  kind?: "currency" | "percent" | "number" | "text";
  detail?: string;
}) {
  const display =
    typeof value === "string"
      ? value
      : kind === "currency"
        ? formatCurrency(value)
        : kind === "percent"
          ? formatPct(value)
          : value.toLocaleString();

  return (
    <div className="min-w-0 rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{label}</div>
      <div className="mt-3 text-2xl font-semibold text-ink">{display}</div>
      {detail ? <div className="mt-2 text-xs text-slate-400">{detail}</div> : null}
    </div>
  );
}
