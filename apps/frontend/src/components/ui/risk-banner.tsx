import type { Alert } from "@/types";
import { formatDateTime } from "@/lib/utils";

export function RiskBanner({
  alerts,
  mode,
  onClear,
  clearBusy = false,
}: {
  alerts: Alert[];
  mode?: string;
  onClear?: () => void | Promise<void>;
  clearBusy?: boolean;
}) {
  const riskAlerts = alerts.filter((alert) => alert.category === "risk" || alert.severity === "warning");
  if (riskAlerts.length === 0) {
    return (
      <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
        Risk engine is active. Live trading stays disabled unless backend configuration explicitly enables it.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="font-semibold uppercase tracking-[0.18em] text-amber-300">Risk Notices</div>
          <div className="mt-1 text-xs text-amber-100/70">
            Showing {Math.min(riskAlerts.length, 5)} of {riskAlerts.length} open {mode ? `${mode} ` : ""}risk/warning notices.
          </div>
        </div>
        {onClear ? (
          <button
            type="button"
            onClick={onClear}
            disabled={clearBusy}
            className="rounded-full border border-amber-400/30 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-100 hover:bg-amber-400/10 disabled:cursor-wait disabled:opacity-60"
            title="Mark the currently open risk notices as resolved. This does not delete audit history."
          >
            {clearBusy ? "Clearing..." : "Clean up notices"}
          </button>
        ) : null}
      </div>
      <div className="mt-2 space-y-2">
        {riskAlerts.slice(0, 5).map((alert) => (
          <div key={alert.id} className="rounded-xl border border-amber-500/15 bg-black/20 px-3 py-2">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
              <div className="font-medium">{alert.title}</div>
              <div className="shrink-0 text-[11px] uppercase tracking-[0.12em] text-amber-100/60">
                {formatDateTime(alert.created_at)}
              </div>
            </div>
            <div className="mt-1 text-xs text-amber-100/80">{alert.message}</div>
            <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.14em] text-amber-100/55">
              <span>{alert.mode || "system"}</span>
              <span>{alert.category}</span>
              <span>{alert.severity}</span>
              {alert.source_ref ? <span>ref {alert.source_ref.slice(0, 8)}</span> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
