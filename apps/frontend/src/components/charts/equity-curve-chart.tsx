"use client";

import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCurrency, formatDateTime } from "@/lib/utils";

export function EquityCurveChart({ data, title }: { data: { timestamp: string; value: number }[]; title?: string }) {
  const values = data.map((item) => Number(item.value)).filter(Number.isFinite);
  const domain = useMemo<[number, number]>(() => {
    if (!values.length) return [0, 1];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.18, Math.abs(max || min) * 0.015, 1);
    return [Math.max(0, min - padding), max + padding];
  }, [values]);

  return (
    <div className="min-w-0 rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{title || "Equity Curve"}</div>
      <div className="h-72">
        {data.length ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 20, bottom: 4, left: 8 }}>
              <CartesianGrid stroke="#1f2a44" vertical={false} />
              <XAxis
                dataKey="timestamp"
                interval="preserveStartEnd"
                minTickGap={28}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                tickFormatter={(value) => shortDate(value)}
              />
              <YAxis
                domain={domain}
                tickCount={5}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                tickFormatter={(value) => formatCompactCurrency(Number(value))}
                width={64}
              />
              <Tooltip
                labelFormatter={(value) => formatDateTime(String(value))}
                formatter={(value: number) => [formatCurrency(Number(value)), "Equity"]}
                contentStyle={{ background: "#020617", border: "1px solid #1f2a44", borderRadius: 8 }}
                labelStyle={{ color: "#cbd5e1" }}
              />
              <Line type="monotone" dataKey="value" stroke="#14b8a6" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-border text-sm text-slate-500">
            No equity snapshots yet.
          </div>
        )}
      </div>
    </div>
  );
}

function shortDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(5, 10);
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short" }).format(date);
}

function formatCompactCurrency(value: number) {
  if (Math.abs(value) < 10_000) {
    return `$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}
