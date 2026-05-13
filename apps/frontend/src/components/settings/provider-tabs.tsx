"use client";

import { useMemo, useState } from "react";

import { useWorkspace } from "@/components/layout/workspace-provider";
import { ProviderForm } from "@/components/settings/provider-form";
import type { ProviderConfig } from "@/types";

interface ProviderTabsProps {
  providers: ProviderConfig[];
  onSaved: (provider: ProviderConfig) => void;
  allowedModes?: string[];
}

export function ProviderTabs({ providers, onSaved, allowedModes }: ProviderTabsProps) {
  const workspace = useWorkspace();
  const workspaceProviders = useMemo(
    () =>
      providers
        .filter(
          (provider) =>
            provider.deployment_scope === workspace.scope &&
            provider.vendor_key === workspace.vendorKey &&
            (!allowedModes?.length || allowedModes.includes(provider.trading_mode))
        )
        .sort((left, right) => {
          const order = { simulation: 0, live: 1 };
          return (order[left.trading_mode as keyof typeof order] ?? 99) - (order[right.trading_mode as keyof typeof order] ?? 99);
        }),
    [allowedModes, providers, workspace.scope, workspace.vendorKey]
  );
  const availableModes = workspaceProviders.map((provider) => provider.trading_mode);
  const defaultMode = availableModes.includes("simulation") ? "simulation" : availableModes[0] || "simulation";
  const [mode, setMode] = useState<string>(defaultMode);
  const provider = workspaceProviders.find((item) => item.trading_mode === mode) || workspaceProviders[0];
  const signalProvider = workspaceProviders.find((item) => item.provider_type === workspace.signalProviderType);
  const liveOnly = allowedModes?.length === 1 && allowedModes[0] === "live";
  const simulationOnly = allowedModes?.length === 1 && allowedModes[0] === "simulation";
  if (!provider) return null;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Workspace provider</div>
        <div className="mt-2 text-lg font-semibold text-slate-100">{workspace.label}</div>
        <div className="mt-1 text-sm text-slate-400">{workspace.description}</div>

        {workspaceProviders.length > 1 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {workspaceProviders.map((item) => (
              <button
                key={item.provider_type}
                onClick={() => setMode(item.trading_mode)}
                className={`rounded-full border px-4 py-2 text-sm ${provider.provider_type === item.provider_type ? "" : "border-border text-slate-300 hover:bg-white/5"}`}
                style={
                  provider.provider_type === item.provider_type
                    ? {
                        borderColor: workspace.theme.accentBorder,
                        backgroundColor: workspace.theme.accentSurface,
                        color: workspace.theme.primary,
                      }
                    : undefined
                }
              >
                {item.mode_label} · {item.enabled ? "Enabled" : "Disabled"}
              </button>
            ))}
          </div>
        ) : null}

        <div className="mt-4 rounded-xl border border-border bg-black/20 p-3 text-sm text-slate-300">
          {liveOnly
            ? "This Live Trading settings tab edits only the guarded actual-trading provider profile for the current workspace."
            : simulationOnly
              ? "This workspace tab edits the simulation provider profile used for signals, model comparison, and replay."
              : "This page is locked to the current workspace. If you want to configure another provider family, open its dedicated port from the quick links at the top of the app."}
        </div>

        <div className="mt-3 rounded-xl border border-border bg-black/20 p-3 text-sm text-slate-300">
          {liveOnly ? (
            <>
              Actual-trading prompts and model health are kept separate from simulation accounts. Live automation still requires this profile to be selected as the one live model.
            </>
          ) : (
            <>
              Signals and simulation features on this port use the <span className="font-semibold text-slate-100">Simulation</span> profile:
              {" "}
              <span className="font-mono text-slate-100">{workspace.signalProviderType}</span>.
              {" "}
              Live trading settings are isolated in the <span className="font-semibold text-slate-100">Live Trading</span> tab.
              {signalProvider ? (
                <>
                  {" "}
                  Current simulation status: <span className="font-semibold text-slate-100">{signalProvider.enabled ? "enabled" : "disabled"}</span>.
                </>
              ) : null}
            </>
          )}
        </div>

        {provider.trading_mode !== "simulation" && !liveOnly ? (
          <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-100">
            You are editing <span className="font-semibold">Actual Trading</span>. The Signals page on this workspace still runs against the
            {" "}
            <span className="font-semibold">Simulation</span> profile.
          </div>
        ) : null}
      </div>

      <ProviderForm key={provider.provider_type} providerType={provider.provider_type} provider={provider} onSaved={onSaved} />
    </div>
  );
}
