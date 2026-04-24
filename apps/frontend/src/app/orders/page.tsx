"use client";

import { useMemo, useState } from "react";

import { TraceButton } from "@/components/provenance/provenance-chips";
import { ProvenanceDialog } from "@/components/provenance/provenance-dialog";
import { TradesTable } from "@/components/trades/trades-table";
import { useApi } from "@/hooks/use-api";
import { useProvenanceTrace } from "@/hooks/use-provenance-trace";
import { api } from "@/lib/api";

export default function OrdersPage() {
  const [mode, setMode] = useState<"all" | "live" | "simulation">("all");
  const provenance = useProvenanceTrace();
  const { data, loading, error } = useApi(async () => {
    const [orders, trades] = await Promise.all([
      api.getOrders(mode === "all" ? undefined : { mode }),
      api.getTrades(mode === "all" ? undefined : { mode }),
    ]);
    return { orders, trades };
  }, [mode]);

  const rejectedOrders = useMemo(() => (data?.orders || []).filter((order) => order.status === "rejected").slice(0, 5), [data?.orders]);

  if (loading || !data) return <div className="text-sm text-slate-400">Loading order blotter...</div>;
  if (error) return <div className="text-sm text-rose-300">Orders failed to load: {error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Orders / Trades</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100">Execution blotter and audit trail</h1>
          <div className="mt-2 text-sm text-slate-400">Manual tickets now live in the dedicated Live Trading and Simulation tabs. This page focuses on history, status, and traceability.</div>
        </div>
        <div className="flex gap-2">
          {(["all", "simulation", "live"] as const).map((value) => (
            <button key={value} type="button" onClick={() => setMode(value)} className={`rounded-full border px-3 py-2 text-xs uppercase tracking-[0.14em] ${mode === value ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-100" : "border-border text-slate-300 hover:bg-white/5"}`}>
              {value}
            </button>
          ))}
        </div>
      </div>

      {rejectedOrders.length ? (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-100 shadow-panel">
          <div className="font-semibold uppercase tracking-[0.18em] text-amber-300">Recent rejected orders</div>
          <div className="mt-3 space-y-2">
            {rejectedOrders.map((order) => (
              <div key={order.id} className="rounded-xl border border-amber-500/15 bg-black/20 px-3 py-2">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="font-medium">{order.symbol} · {order.side.toUpperCase()}</div>
                  <TraceButton label="Trace" onClick={() => provenance.openTrace({ type: "order", id: order.id })} />
                </div>
                <div className="text-xs text-amber-100/80">{order.rejection_reason || "Rejected without a detailed reason."}</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <section>
        <div className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Orders</div>
        <TradesTable orders={data.orders} onViewTrace={(type, item) => provenance.openTrace({ type, id: item.id })} />
      </section>

      <section>
        <div className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Trades</div>
        <TradesTable trades={data.trades} onViewTrace={(type, item) => provenance.openTrace({ type, id: item.id })} />
      </section>

      <ProvenanceDialog
        open={Boolean(provenance.target)}
        signal={provenance.signal}
        trace={provenance.trace}
        loading={provenance.loading}
        error={provenance.error}
        onClose={provenance.closeTrace}
      />
    </div>
  );
}
