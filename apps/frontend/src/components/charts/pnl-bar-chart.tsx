"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCurrency } from "@/lib/utils";

export function PnlBarChart({ data, title }: { data: { name: string; value: number }[]; title: string }) {
  const cleaned = data
    .map((item) => ({ name: item.name || "unknown", value: Number(item.value) || 0 }))
    .filter((item) => Number.isFinite(item.value) && Math.abs(item.value) > 0.0001);
  const values = cleaned.map((item) => item.value);
  const maxAbs = values.length ? Math.max(...values.map((value) => Math.abs(value))) : 0;
  const domain: [number, number] = maxAbs ? [-maxAbs * 1.15, maxAbs * 1.15] : [-1, 1];

  return (
    <div className="min-w-0 rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{title}</div>
      <div className="h-72">
        {cleaned.length ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={cleaned} margin={{ top: 8, right: 20, bottom: 12, left: 8 }}>
              <CartesianGrid stroke="#1f2a44" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#1f2a44" }} />
              <YAxis
                domain={domain}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                tickFormatter={(value) => formatCurrency(Number(value))}
                tickLine={false}
                axisLine={{ stroke: "#1f2a44" }}
                width={72}
              />
              <Tooltip
                formatter={(value: number) => [formatCurrency(Number(value)), "Realized PnL"]}
                contentStyle={{ background: "#020617", border: "1px solid #1f2a44", borderRadius: 8 }}
                labelStyle={{ color: "#cbd5e1" }}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]} isAnimationActive={false}>
                {cleaned.map((item) => (
                  <Cell key={item.name} fill={item.value >= 0 ? "#22d3ee" : "#fb7185"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-border text-sm text-slate-500">
            No realized PnL yet.
          </div>
        )}
      </div>
    </div>
  );
}
