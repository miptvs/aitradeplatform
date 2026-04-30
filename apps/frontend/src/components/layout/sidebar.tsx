"use client";

import { CSSProperties } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, BookOpen, CandlestickChart, ChartNoAxesCombined, ChevronsLeft, ChevronsRight, Cpu, Layers3, Newspaper, Settings2, ShieldAlert, SplitSquareVertical, Waypoints } from "lucide-react";

import { useWorkspace } from "@/components/layout/workspace-provider";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/live", label: "Live Trading", icon: CandlestickChart },
  { href: "/simulation", label: "Simulation", icon: SplitSquareVertical },
  { href: "/positions/live", label: "Live Positions", icon: Layers3 },
  { href: "/positions/simulation", label: "Simulation Positions", icon: SplitSquareVertical },
  { href: "/orders", label: "Orders / Trades", icon: CandlestickChart },
  { href: "/signals", label: "Signals", icon: Waypoints },
  { href: "/analytics", label: "Analytics", icon: ChartNoAxesCombined },
  { href: "/news", label: "News / Intelligence", icon: Newspaper },
  { href: "/architecture", label: "Architecture", icon: Cpu },
  { href: "/settings", label: "Settings", icon: Settings2 },
  { href: "/api-docs-link", label: "API Docs", icon: BookOpen }
];

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const pathname = usePathname();
  const workspace = useWorkspace();
  const heroStyle: CSSProperties = {
    backgroundImage: workspace.theme.sidebarBackground,
  };
  return (
    <aside className={cn("flex h-full flex-col rounded-[28px] border border-border bg-slate-950/85 shadow-panel transition-all", collapsed ? "p-3" : "p-4")}>
      <div className={cn("rounded-2xl border", collapsed ? "p-3" : "p-4")} style={{ ...heroStyle, borderColor: workspace.theme.accentBorder }}>
        <div className={cn("flex items-start justify-between gap-2", collapsed ? "flex-col items-center" : "")}>
          <div className={cn(collapsed ? "text-center" : "")}>
            <div className="text-[11px] uppercase tracking-[0.22em]" style={{ color: workspace.theme.primary }}>{collapsed ? "AI" : "AI Trader"}</div>
            {!collapsed ? <div className="mt-2 text-lg font-semibold text-slate-100">{workspace.label}</div> : null}
          </div>
          <button
            type="button"
            onClick={onToggle}
            className="rounded-xl border border-border p-2 text-slate-300 hover:bg-white/5 hover:text-slate-100"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar to icons only"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar to icons only"}
          >
            {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
          </button>
        </div>
        {collapsed ? (
          <div className="mt-3 flex justify-center text-slate-400" title="Live execution disabled by default">
            <ShieldAlert size={16} />
          </div>
        ) : (
          <>
            <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
              <ShieldAlert size={14} />
              Live execution disabled by default
            </div>
            <div className="mt-2 text-xs text-slate-500">Workspace port :{workspace.port}</div>
          </>
        )}
      </div>
      <nav className="mt-6 space-y-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              title={label}
              className={cn(
                "flex items-center rounded-2xl border text-sm transition",
                collapsed ? "justify-center px-2 py-3" : "gap-3 px-3 py-3",
                active ? "text-slate-50" : "border-transparent bg-transparent text-slate-400 hover:border-border hover:bg-white/5 hover:text-slate-100"
              )}
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
              <Icon size={collapsed ? 18 : 16} />
              {!collapsed ? <span>{label}</span> : null}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
