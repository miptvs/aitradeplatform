"use client";

import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";

export function ActionMenu({ label = "Actions", children }: { label?: string; children: ReactNode }) {
  return (
    <details className="group relative">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-full border border-border bg-black/20 px-3 py-2 text-xs uppercase tracking-[0.16em] text-slate-300 hover:bg-white/5">
        {label}
        <ChevronDown size={14} className="transition group-open:rotate-180" />
      </summary>
      <div className="absolute right-0 top-12 z-20 w-56 rounded-2xl border border-border bg-slate-950/95 p-2 shadow-panel">
        {children}
      </div>
    </details>
  );
}

export function ActionMenuButton({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm text-slate-200 hover:bg-white/5 ${
        props.className || ""
      }`}
    >
      {children}
    </button>
  );
}
