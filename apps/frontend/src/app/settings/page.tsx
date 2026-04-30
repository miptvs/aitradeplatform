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
import type { BrokerAccount, ProviderConfig, SettingsOverview, TradingAutomationProfile } from "@/types";

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
  if (rule.rule_type === "cash_reserve") {
    const reservePct = Number(rule.config_json.min_cash_reserve_pct ?? 0);
    return `Keeps ${formatPct(reservePct)} of account value as cash before new buys or simulated shorts.`;
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

function summarizeAutomation(profile: TradingAutomationProfile) {
  return `${profile.approval_mode.split("_").join(" ")} · threshold ${formatPct(profile.confidence_threshold)} · ${profile.default_order_notional.toFixed(0)} default notional`;
}

function toAutomationPayload(profile: TradingAutomationProfile) {
  return {
    enabled: profile.enabled,
    automation_enabled: profile.automation_enabled,
    scheduled_execution_enabled: profile.scheduled_execution_enabled,
    execution_interval_seconds: profile.execution_interval_seconds,
    inherit_from_live: profile.inherit_from_live,
    approval_mode: profile.approval_mode,
    allowed_strategy_slugs: profile.allowed_strategy_slugs,
    tradable_actions: profile.tradable_actions,
    allowed_provider_types: profile.allowed_provider_types,
    confidence_threshold: profile.confidence_threshold,
    default_order_notional: profile.default_order_notional,
    stop_loss_pct: profile.stop_loss_pct,
    take_profit_pct: profile.take_profit_pct,
    trailing_stop_pct: profile.trailing_stop_pct,
    max_orders_per_run: profile.max_orders_per_run,
    risk_profile: profile.risk_profile,
    notes: profile.notes,
    config_json: profile.config_json,
  };
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

  async function handleSimulationInheritanceChange(checked: boolean) {
    if (!settingsState) return;
    const saved = await api.saveSimulationAutomation({
      ...toAutomationPayload(settingsState.simulation_automation),
      inherit_from_live: checked,
    });
    setMessage(checked ? "Simulation now inherits the live automation policy." : "Simulation now uses its own automation overrides.");
    setSettingsState((current) => {
      if (!current) return current;
      return {
        ...current,
        simulation_automation: saved,
      };
    });
  }

  async function handleLiveModelChange(providerType: string) {
    if (!settingsState) return;
    const saved = await api.saveLiveAutomation({
      ...toAutomationPayload(settingsState.live_automation),
      allowed_provider_types: providerType ? [providerType] : [],
      config_json: {
        ...settingsState.live_automation.config_json,
        live_model_provider_type: providerType || null,
      },
    });
    setMessage(providerType ? `Live trading model locked to ${providerType}.` : "Live trading model cleared; live automation is blocked until one is selected.");
    setSettingsState((current) => (current ? { ...current, live_automation: saved } : current));
  }

  if (loading && !settingsState) return <div className="text-sm text-slate-400">Loading settings...</div>;
  if (error && !settingsState) return <div className="text-sm text-rose-300">Settings failed to load: {error}</div>;
  if (!settingsState) return <div className="text-sm text-slate-400">Loading settings...</div>;

  const trading212Account = brokerAccountsState.find((account) => account.broker_type === "trading212");
  const liveProviders = settingsState.providers.filter((provider) => provider.trading_mode === "live");
  const configuredLiveProvider = String(settingsState.live_automation.config_json.live_model_provider_type || settingsState.live_automation.allowed_provider_types[0] || "");

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

      <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Live trading model</div>
            <div className="mt-1 text-sm text-slate-400">
              Only this one model/profile may generate or approve live trading decisions. Simulation can still run many model accounts side by side.
            </div>
          </div>
          <StatusBadge status={configuredLiveProvider ? "locked" : "blocked"} />
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr,auto]">
          <select
            value={configuredLiveProvider}
            onChange={(event) => handleLiveModelChange(event.target.value)}
            className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100"
          >
            <option value="">No live model selected</option>
            {liveProviders.map((provider) => (
              <option key={provider.provider_type} value={provider.provider_type}>
                {provider.vendor_name} · {provider.provider_type} · {provider.default_model || "model not set"}
              </option>
            ))}
          </select>
          <div className="rounded-xl border border-border bg-black/20 px-4 py-2 text-sm text-slate-300">
            {configuredLiveProvider ? "Server-side live automation is locked to this profile." : "Live automation is disabled until a live model is selected."}
          </div>
        </div>
      </div>

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
          <div className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Automation parity</div>
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-xl border border-border bg-black/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium text-slate-100">Live automation</div>
                  <div className="mt-1 text-xs text-slate-400">This is the guarded production policy used by the Live Trading workspace.</div>
                </div>
                <StatusBadge status={settingsState.live_automation.automation_enabled ? "enabled" : "disabled"} />
              </div>
              <div className="mt-3 text-sm text-slate-200">{summarizeAutomation(settingsState.live_automation)}</div>
            </div>
            <div className="rounded-xl border border-border bg-black/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium text-slate-100">Simulation automation</div>
                  <div className="mt-1 text-xs text-slate-400">
                    Use the same policy as Live when you want training and production review to stay aligned. Turn it off when you want a safe override for experimentation.
                  </div>
                </div>
                <StatusBadge status={settingsState.simulation_automation.inherit_from_live ? "shared" : "custom"} />
              </div>
              <label className="mt-4 flex items-center justify-between rounded-xl border border-border px-3 py-3">
                <div>
                  <div className="text-sm font-medium text-slate-100">Use same settings as Live</div>
                  <div className="mt-1 text-xs text-slate-400">
                    This keeps Simulation on the same strategy, threshold, sizing, and stop defaults as the live automation profile.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={settingsState.simulation_automation.inherit_from_live}
                  onChange={(event) => handleSimulationInheritanceChange(event.target.checked)}
                  className="h-4 w-4 rounded border-border bg-slate-900"
                />
              </label>
              <div className="mt-3 text-sm text-slate-200">
                {settingsState.simulation_automation.inherit_from_live
                  ? `Currently inheriting from ${settingsState.simulation_automation.effective_source_mode}. ${summarizeAutomation(settingsState.simulation_automation)}`
                  : summarizeAutomation(settingsState.simulation_automation)}
              </div>
            </div>
          </div>

          <div className="mb-4 mt-6 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Operational notes</div>
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
