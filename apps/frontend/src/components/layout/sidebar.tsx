"use client";

import { CSSProperties } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, BookOpen, CandlestickChart, ChartNoAxesCombined, Cpu, Layers3, Newspaper, Settings2, ShieldAlert, SplitSquareVertical, Waypoints } from "lucide-react";

import { useWorkspace } from "@/components/layout/workspace-provider";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/live", label: "Live Trading", icon: CandlestickChart },
  { href: "/simulation", label: "Simulation", icon: SplitSquareVertical },
  { href: "/positions", label: "Positions", icon: Layers3 },
  { href: "/orders", label: "Orders / Trades", icon: CandlestickChart },
  { href: "/signals", label: "Signals", icon: Waypoints },
  { href: "/analytics", label: "Analytics", icon: ChartNoAxesCombined },
  { href: "/news", label: "News / Intelligence", icon: Newspaper },
  { href: "/architecture", label: "Architecture", icon: Cpu },
  { href: "/settings", label: "Settings", icon: Settings2 },
  { href: "/api-docs-link", label: "API Docs", icon: BookOpen }
];

export function Sidebar() {
  const pathname = usePathname();
  const workspace = useWorkspace();
  const heroStyle: CSSProperties = {
    backgroundImage: workspace.theme.sidebarBackground,
  };
  return (
    <aside className="flex h-full flex-col rounded-[28px] border border-border bg-slate-950/85 p-4 shadow-panel">
      <div className="rounded-2xl border p-4" style={{ ...heroStyle, borderColor: workspace.theme.accentBorder }}>
        <div className="text-[11px] uppercase tracking-[0.22em]" style={{ color: workspace.theme.primary }}>AI Trader</div>
        <div className="mt-2 text-lg font-semibold text-slate-100">{workspace.label}</div>
        <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
          <ShieldAlert size={14} />
          Live execution disabled by default
        </div>
        <div className="mt-2 text-xs text-slate-500">Workspace port :{workspace.port}</div>
      </div>
      <nav className="mt-6 space-y-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn("flex items-center gap-3 rounded-2xl border px-3 py-3 text-sm transition", active ? "text-slate-50" : "border-transparent bg-transparent text-slate-400 hover:border-border hover:bg-white/5 hover:text-slate-100")}
              style={
                active
                  ? {
                      borderColor: workspace.theme.accentBorder,
                      backgroundColor: workspace.theme.accentSurface,
                      color: workspace.theme.primary,
                    }
                  : undefined
              }
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
