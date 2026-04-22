"use client";

import { useEffect, useState } from "react";

import { useWorkspace } from "@/components/layout/workspace-provider";
import { ProviderTabs } from "@/components/settings/provider-tabs";
import { RiskRuleEditor } from "@/components/settings/risk-rule-editor";
import { Trading212Form } from "@/components/settings/trading212-form";
import { StatusBadge } from "@/components/ui/status-badge";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatPct } from "@/lib/utils";
import type { BrokerAccount, ProviderConfig, SettingsOverview } from "@/types";

function summarizeRiskRule(rule: SettingsOverview["risk_rules"][number]) {
  if (rule.rule_type === "daily_max_loss") {
    const limitPct = Number(rule.config_json.max_daily_loss_pct ?? 0);
    if (limitPct > 0) {
      return `Blocks new orders once daily loss reaches ${formatPct(limitPct)} of total account value.`;
    }
  }
  if (rule.rule_type === "max_capital_per_asset") {
    const maxPct = Number(rule.config_json.max_pct ?? 0);
    if (maxPct > 0) {
      return `Limits any single asset to ${formatPct(maxPct)} of account value.`;
    }
  }
  if (rule.rule_type === "max_sector_exposure") {
    const maxSectorPct = Number(rule.config_json.max_sector_pct ?? 0);
    if (maxSectorPct > 0) {
      return `Limits total sector exposure to ${formatPct(maxSectorPct)} of account value.`;
    }
  }
  if (rule.rule_type === "max_drawdown_halt") {
    const drawdownPct = Number(rule.config_json.max_drawdown_pct ?? 0);
    if (drawdownPct > 0) {
      return `Stops new orders if peak-to-trough drawdown exceeds ${formatPct(drawdownPct)}.`;
    }
  }
  if (rule.rule_type === "per_trade_risk") {
    const riskPct = Number(rule.config_json.max_risk_pct ?? 0);
    if (riskPct > 0) {
      return `Caps risk on each trade at ${formatPct(riskPct)} of the reference account value.`;
    }
  }
  return null;
}

export default function SettingsPage() {
  const workspace = useWorkspace();
  const { data, loading, error } = useApi(async () => {
    const [settings, brokerAccounts] = await Promise.all([api.getSettingsOverview(), api.getBrokerAccounts()]);
    return { settings, brokerAccounts };
  });
  const [settingsState, setSettingsState] = useState<SettingsOverview | null>(null);
  const [brokerAccountsState, setBrokerAccountsState] = useState<BrokerAccount[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!data) return;
    setSettingsState(data.settings);
    setBrokerAccountsState(data.brokerAccounts);
  }, [data]);

  async function handleProviderSaved(saved: ProviderConfig) {
    setMessage("Provider settings saved.");
    setSettingsState((current) => {
      if (!current) return current;
      return {
        ...current,
        providers: current.providers.map((provider) => (provider.provider_type === saved.provider_type ? saved : provider)),
      };
    });
  }

  async function handleBrokerSaved(saved: BrokerAccount) {
    setMessage("Trading212 settings saved.");
    setBrokerAccountsState((current) => {
      const existing = current.find((account) => account.id === saved.id);
      if (existing) {
        return current.map((account) => (account.id === saved.id ? saved : account));
      }
      return [...current, saved];
    });
  }

  async function handleRiskRuleSaved(saved: SettingsOverview["risk_rules"][number]) {
    setMessage("Risk rule saved.");
    setSettingsState((current) => {
      if (!current) return current;
      return {
        ...current,
        risk_rules: current.risk_rules.map((rule) => (rule.id === saved.id ? saved : rule)),
      };
    });
  }

  if (loading && !settingsState) return <div className="text-sm text-slate-400">Loading settings...</div>;
  if (error && !settingsState) return <div className="text-sm text-rose-300">Settings failed to load: {error}</div>;
  if (!settingsState) return <div className="text-sm text-slate-400">Loading settings...</div>;

  const trading212Account = brokerAccountsState.find((account) => account.broker_type === "trading212");

  return (
    <div className="space-y-6">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Settings</div>
        <h1 className="mt-1 text-2xl font-semibold text-slate-100">Workspace model configuration</h1>
      </div>

      {message ? <div className="rounded-xl border border-border bg-panel/90 px-4 py-3 text-sm text-slate-200">{message}</div> : null}

      <div className="rounded-2xl border border-border bg-panel/90 px-4 py-3 text-sm text-slate-300 shadow-panel">
        This entrypoint is centered on <span className="font-semibold text-slate-100">{workspace.label}</span>. Cross-provider switching and per-task routing are intentionally hidden here so this port only edits its own model workspace.
      </div>

      <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
        Live trading backend switch: <span className="font-semibold">{settingsState.live_trading_enabled ? "enabled" : "disabled"}</span>. Even if enabled later, every live order still passes risk validation and broker capability checks.
      </div>

      <ProviderTabs providers={settingsState.providers} onSaved={handleProviderSaved} />

      <Trading212Form account={trading212Account} onSaved={handleBrokerSaved} />

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Risk rules</div>
          <div className="space-y-3">
            {settingsState.risk_rules.map((rule) => (
              (() => {
                const summary = summarizeRiskRule(rule);
                return (
                  <div key={rule.id} className="rounded-xl border border-border bg-black/20 p-3">
                    <div className="flex items-center justify-between">
                      <div className="font-medium text-slate-100">{rule.name}</div>
                      <StatusBadge status={rule.enabled ? "ok" : "warn"} />
                    </div>
                    <div className="mt-2 text-xs text-slate-400">{rule.description || rule.rule_type}</div>
                    {summary ? <div className="mt-2 text-sm text-slate-200">{summary}</div> : null}
                    <RiskRuleEditor rule={rule} onSaved={handleRiskRuleSaved} />
                    <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-950/80 p-2 font-mono text-[11px] text-slate-300">
                      {JSON.stringify(rule.config_json, null, 2)}
                    </pre>
                  </div>
                );
              })()
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Operational notes</div>
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-xl border border-border bg-black/20 p-3">
              Trading212 credentials can now be saved here for backend-only ticker validation. Execution remains intentionally scaffolded.
            </div>
            <div className="rounded-xl border border-border bg-black/20 p-3">
              Watchlists, assets universe, and simulation parameters are stored locally and survive container restarts through Postgres volumes.
            </div>
            <div className="rounded-xl border border-border bg-black/20 p-3">
              Provider secrets are write-only from the UI. Saved keys are encrypted in the backend database before persistence.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
