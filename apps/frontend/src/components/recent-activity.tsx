import type { Order, Signal, Trade } from "@/types";

export function RecentActivity({ orders, trades, signals }: { orders: Order[]; trades: Trade[]; signals: Signal[] }) {
  const items = [
    ...orders.slice(0, 4).map((order) => ({ id: `order-${order.id}`, label: `${order.symbol} order ${order.status}`, meta: order.created_at })),
    ...trades.slice(0, 4).map((trade) => ({ id: `trade-${trade.id}`, label: `${trade.symbol} ${trade.side} ${trade.quantity}`, meta: trade.executed_at })),
    ...signals.slice(0, 4).map((signal) => ({ id: `signal-${signal.id}`, label: `${signal.symbol} ${signal.action} ${Math.round(signal.confidence * 100)}%`, meta: signal.occurred_at }))
  ]
    .sort((a, b) => b.meta.localeCompare(a.meta))
    .slice(0, 8);

  return (
    <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Recent Activity</div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.id} className="rounded-xl border border-border bg-black/20 px-3 py-2">
            <div className="text-sm font-medium text-slate-100">{item.label}</div>
            <div className="text-xs text-slate-400">{item.meta.slice(0, 16).replace("T", " ")}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
