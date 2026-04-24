"use client";

import { CSSProperties, PropsWithChildren, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { Sidebar } from "@/components/layout/sidebar";
import { useWorkspace } from "@/components/layout/workspace-provider";
import { StatusBadge } from "@/components/ui/status-badge";
import { useEventStream } from "@/hooks/use-event-stream";
import { cn } from "@/lib/utils";

export function AppShell({ children }: PropsWithChildren) {
  const { connected, events } = useEventStream();
  const pathname = usePathname();
  const workspace = useWorkspace();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const latest = events[0];
  const remoteLinks = workspace.links.filter((link) => link.scope === "remote");
  const localLinks = workspace.links.filter((link) => link.scope === "local");
  const shellStyle: CSSProperties = {
    backgroundImage: workspace.theme.shellBackground,
  };
  const panelStyle: CSSProperties = {
    boxShadow: workspace.theme.panelGlow,
  };

  useEffect(() => {
    const saved = window.localStorage.getItem("ai-trader-sidebar-collapsed");
    if (saved === "true") setSidebarCollapsed(true);
  }, []);

  function toggleSidebar() {
    setSidebarCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("ai-trader-sidebar-collapsed", String(next));
      return next;
    });
  }

  return (
    <div className="min-h-screen px-4 py-4 text-ink md:px-6" style={shellStyle}>
      <div className={cn("mx-auto grid max-w-[1680px] gap-4 transition-[grid-template-columns]", sidebarCollapsed ? "lg:grid-cols-[88px_1fr]" : "lg:grid-cols-[280px_1fr]")}>
        <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} />
        <main className="rounded-[28px] border border-border bg-slate-950/60 p-4 shadow-panel backdrop-blur md:p-6" style={panelStyle}>
          <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-border bg-panel/70 px-4 py-4 lg:flex-row lg:items-center lg:justify-between" style={panelStyle}>
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Operator Console</div>
              <div className="mt-1 text-xl font-semibold text-slate-100">AI-assisted trading, portfolio analysis, and simulation</div>
              <div className="mt-2 text-sm text-slate-300">
                Active workspace: <span className="font-semibold" style={{ color: workspace.theme.primary }}>{workspace.label}</span>
              </div>
              <div className="mt-1 text-xs text-slate-400">{workspace.description}</div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge status={connected ? "ok" : "warn"} />
              <div className="rounded-full border border-border px-3 py-1 text-xs text-slate-300">SSE {connected ? "connected" : "reconnecting"}</div>
              {latest ? (
                <div className="max-w-[420px] truncate rounded-full border border-border px-3 py-1 text-xs text-slate-300">
                  {latest.event}: {JSON.stringify(latest.payload)}
                </div>
              ) : null}
            </div>
          </div>
          <div className="mb-6 space-y-3 rounded-2xl border border-border bg-panel/70 px-4 py-4 shadow-panel" style={panelStyle}>
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Workspace Links</div>
            <div className="flex flex-col gap-3">
              <WorkspaceLinkRow title="Remote models" currentKey={workspace.key} currentPath={pathname} links={remoteLinks} activeColor={workspace.theme.primary} activeSurface={workspace.theme.accentSurface} activeBorder={workspace.theme.accentBorder} />
              <WorkspaceLinkRow title="Local models" currentKey={workspace.key} currentPath={pathname} links={localLinks} activeColor={workspace.theme.primary} activeSurface={workspace.theme.accentSurface} activeBorder={workspace.theme.accentBorder} />
            </div>
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

function WorkspaceLinkRow({
  title,
  currentKey,
  currentPath,
  links,
  activeColor,
  activeSurface,
  activeBorder,
}: {
  title: string;
  currentKey: string;
  currentPath: string;
  links: Array<{ key: string; label: string; port: number; origin: string }>;
  activeColor: string;
  activeSurface: string;
  activeBorder: string;
}) {
  return (
    <div className="flex flex-col gap-2 xl:flex-row xl:items-center">
      <div className="w-[140px] text-xs uppercase tracking-[0.18em] text-slate-500">{title}</div>
      <div className="flex flex-wrap gap-2">
        {links.map((link) => {
          const active = currentKey === link.key;
          return (
            <a
              key={link.key}
              href={`${link.origin}${currentPath}`}
              aria-current={active ? "page" : undefined}
              className={`rounded-full border px-3 py-2 text-xs tracking-[0.12em] transition ${
                active ? "" : "border-border text-slate-300 hover:bg-white/5 hover:text-slate-100"
              }`}
              style={
                active
                  ? {
                      borderColor: activeBorder,
                      backgroundColor: activeSurface,
                      color: activeColor,
                    }
                  : undefined
              }
            >
              {link.label} :{link.port}
            </a>
          );
        })}
      </div>
    </div>
  );
}
