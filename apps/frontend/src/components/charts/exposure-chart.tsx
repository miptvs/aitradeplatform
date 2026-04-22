"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = ["#14b8a6", "#38bdf8", "#f59e0b", "#f43f5e", "#8b5cf6", "#22c55e"];

export function ExposureChart({ data }: { data: { name: string; value: number }[] }) {
  return (
    <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Exposure Mix</div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" outerRadius={100} innerRadius={56} paddingAngle={4}>
              {data.map((entry, index) => (
                <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
