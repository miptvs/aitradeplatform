import type { Alert } from "@/types";

export function RiskBanner({ alerts }: { alerts: Alert[] }) {
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
      <div className="font-semibold uppercase tracking-[0.18em] text-amber-300">Risk Notices</div>
      <div className="mt-2 space-y-2">
        {riskAlerts.slice(0, 3).map((alert) => (
          <div key={alert.id} className="rounded-xl border border-amber-500/15 bg-black/20 px-3 py-2">
            <div className="font-medium">{alert.title}</div>
            <div className="text-xs text-amber-100/80">{alert.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
