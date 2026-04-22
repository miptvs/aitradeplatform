"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCurrency } from "@/lib/utils";

export function EquityCurveChart({ data, title }: { data: { timestamp: string; value: number }[]; title?: string }) {
  return (
    <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{title || "Equity Curve"}</div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="equityFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#14b8a6" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#14b8a6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1f2a44" vertical={false} />
            <XAxis dataKey="timestamp" tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={(value) => value.slice(5, 10)} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={(value) => `$${Math.round(value / 1000)}k`} />
            <Tooltip formatter={(value: number) => formatCurrency(value)} />
            <Area type="monotone" dataKey="value" stroke="#14b8a6" fill="url(#equityFill)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
