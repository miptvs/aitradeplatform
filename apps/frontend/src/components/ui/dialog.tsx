"use client";

import type { PropsWithChildren, ReactNode } from "react";

export function Dialog({
  open,
  title,
  description,
  actions,
  children,
}: PropsWithChildren<{ open: boolean; title: string; description?: string; actions?: ReactNode }>) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-8 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-3xl border border-border bg-slate-950 p-5 shadow-panel">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{title}</div>
            {description ? <div className="mt-2 text-sm text-slate-400">{description}</div> : null}
          </div>
          {actions}
        </div>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}
