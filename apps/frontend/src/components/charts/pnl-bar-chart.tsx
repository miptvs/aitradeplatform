"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function PnlBarChart({ data, title }: { data: { name: string; value: number }[]; title: string }) {
  return (
    <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{title}</div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid stroke="#1f2a44" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
            <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="value" fill="#38bdf8" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
