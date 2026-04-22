import { Info } from "lucide-react";

export function HelpTooltip({ label, help }: { label: string; help: string }) {
  return (
    <div className="flex items-center gap-2">
      <span>{label}</span>
      <span
        title={help}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-border bg-black/20 text-slate-400 hover:text-slate-100"
      >
        <Info size={12} />
      </span>
    </div>
  );
}
