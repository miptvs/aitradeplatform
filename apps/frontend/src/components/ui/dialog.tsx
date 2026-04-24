"use client";

import type { PropsWithChildren, ReactNode } from "react";

export function Dialog({
  open,
  title,
  description,
  actions,
  size = "default",
  children,
}: PropsWithChildren<{ open: boolean; title: string; description?: string; actions?: ReactNode; size?: "default" | "wide" }>) {
  if (!open) return null;
  const maxWidth = size === "wide" ? "max-w-7xl" : "max-w-2xl";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/80 px-4 py-4 backdrop-blur-sm md:py-8">
      <div className={`flex max-h-[calc(100vh-2rem)] w-full ${maxWidth} flex-col rounded-3xl border border-border bg-slate-950 p-5 shadow-panel md:max-h-[calc(100vh-4rem)]`}>
        <div className="flex shrink-0 items-start justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{title}</div>
            {description ? <div className="mt-2 text-sm text-slate-400">{description}</div> : null}
          </div>
          {actions}
        </div>
        <div className="mt-5 overflow-y-auto pr-1">{children}</div>
      </div>
    </div>
  );
}
