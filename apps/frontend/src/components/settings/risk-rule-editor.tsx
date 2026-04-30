"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatCurrency, formatPct, formatQuantity } from "@/lib/utils";
import type { RiskRule } from "@/types";

interface RiskRuleEditorProps {
  rule: RiskRule;
  onSaved: (rule: RiskRule) => void;
}

type FieldKind = "percent" | "number" | "integer" | "boolean";
type FieldValue = number | boolean;

interface FieldSpec {
  key: string;
  label: string;
  kind: FieldKind;
  help: string;
  min?: number;
  step?: number;
}

const FIELD_SPECS: Record<string, FieldSpec[]> = {
  kill_switch: [
    {
      key: "active",
      label: "Kill switch active",
      kind: "boolean",
      help: "Blocks new orders immediately while this switch is on.",
    },
  ],
  max_position_size: [
    {
      key: "max_notional",
      label: "Max position notional",
      kind: "number",
      min: 0,
      step: 100,
      help: "Maximum size of a single position in account-currency notional.",
    },
    {
      key: "max_quantity",
      label: "Max quantity",
      kind: "number",
      min: 0,
      step: 0.01,
      help: "Maximum units or shares allowed for a single position.",
    },
  ],
  max_capital_per_asset: [
    {
      key: "max_pct",
      label: "Max capital per asset (%)",
      kind: "percent",
      min: 0,
      step: 0.1,
      help: "Share of total account value that any one asset can consume.",
    },
  ],
  max_open_positions: [
    {
      key: "max_open_positions",
      label: "Max open positions",
      kind: "integer",
      min: 0,
      step: 1,
      help: "Maximum number of simultaneously open positions.",
    },
  ],
  max_sector_exposure: [
    {
      key: "max_sector_pct",
      label: "Max sector exposure (%)",
      kind: "percent",
      min: 0,
      step: 0.1,
      help: "Maximum share of total account value that can be concentrated in one sector.",
    },
  ],
  cash_reserve: [
    {
      key: "min_cash_reserve_pct",
      label: "Always keep cash (%)",
      kind: "percent",
      min: 0,
      step: 0.5,
      help: "Keeps this percentage of portfolio value uninvested as cash. Orders that would use this reserve are blocked or must be reduced.",
    },
  ],
  daily_max_loss: [
    {
      key: "max_daily_loss_pct",
      label: "Daily loss limit (%)",
      kind: "percent",
      min: 0,
      step: 0.1,
      help: "Measured against the overall account value. Example: 2.5 means trading pauses after a 2.5% daily loss.",
    },
  ],
  max_drawdown_halt: [
    {
      key: "max_drawdown_pct",
      label: "Max drawdown halt (%)",
      kind: "percent",
      min: 0,
      step: 0.1,
      help: "Stops new orders once the account falls this far from its peak value.",
    },
  ],
  loss_streak_cooldown: [
    {
      key: "loss_streak",
      label: "Loss streak threshold",
      kind: "integer",
      min: 1,
      step: 1,
      help: "How many consecutive losing trades trigger the cooldown.",
    },
    {
      key: "cooldown_minutes",
      label: "Cooldown minutes",
      kind: "integer",
      min: 0,
      step: 1,
      help: "How long new orders stay blocked after the loss streak is hit.",
    },
  ],
  per_trade_risk: [
    {
      key: "max_risk_pct",
      label: "Per-trade risk (%)",
      kind: "percent",
      min: 0,
      step: 0.1,
      help: "Maximum allowed loss from entry to stop, as a share of the reference account value.",
    },
    {
      key: "reference_account_value",
      label: "Reference account value",
      kind: "number",
      min: 0,
      step: 100,
      help: "Used in this MVP to convert per-trade risk percent into an amount.",
    },
    {
      key: "require_stop_loss",
      label: "Require stop loss",
      kind: "boolean",
      help: "If enabled, orders without a stop loss fail this risk check.",
    },
  ],
  market_hours: [
    {
      key: "enforce_market_hours",
      label: "Enforce market hours",
      kind: "boolean",
      help: "Blocks new orders outside the configured market-hours window.",
    },
  ],
};

function toEditorValue(spec: FieldSpec, rawValue: unknown): FieldValue {
  if (spec.kind === "boolean") {
    return Boolean(rawValue);
  }
  const numericValue = Number(rawValue ?? 0);
  if (spec.kind === "percent") {
    return numericValue * 100;
  }
  if (spec.kind === "integer") {
    return Math.trunc(numericValue);
  }
  return numericValue;
}

function normalizeEditorValue(spec: FieldSpec, rawValue: FieldValue): number | boolean {
  if (spec.kind === "boolean") {
    return Boolean(rawValue);
  }
  const numericValue = Number(rawValue ?? 0);
  if (spec.kind === "percent") {
    return Math.max(0, numericValue) / 100;
  }
  if (spec.kind === "integer") {
    return Math.max(0, Math.trunc(numericValue));
  }
  return Math.max(0, numericValue);
}

function buildDraftConfig(rule: RiskRule): Record<string, FieldValue> {
  const specs = FIELD_SPECS[rule.rule_type] || [];
  return Object.fromEntries(specs.map((spec) => [spec.key, toEditorValue(spec, rule.config_json[spec.key])]));
}

function buildRuleDescription(ruleType: string, config: Record<string, unknown>, fallback?: string | null) {
  switch (ruleType) {
    case "kill_switch":
      return Boolean(config.active)
        ? "Global hard stop for order flow. New orders remain blocked while the kill switch is active."
        : "Global hard stop for order flow.";
    case "max_position_size":
      return `Limit a single position to ${formatCurrency(Number(config.max_notional ?? 0))} notional and ${formatQuantity(Number(config.max_quantity ?? 0), 2)} units.`;
    case "max_capital_per_asset":
      return `Limit any single asset to ${formatPct(Number(config.max_pct ?? 0))} of total account value.`;
    case "max_open_positions":
      return `Limit open book size to ${formatQuantity(Number(config.max_open_positions ?? 0), 0)} positions.`;
    case "max_sector_exposure":
      return `Limit total sector exposure to ${formatPct(Number(config.max_sector_pct ?? 0))} of total account value.`;
    case "cash_reserve":
      return `Keep at least ${formatPct(Number(config.min_cash_reserve_pct ?? 0))} of account value in cash before allowing new buys or simulated shorts.`;
    case "daily_max_loss":
      return `Pause new orders after daily losses reach ${formatPct(Number(config.max_daily_loss_pct ?? 0))} of total account value.`;
    case "max_drawdown_halt":
      return `Stop new orders under ${formatPct(Number(config.max_drawdown_pct ?? 0))} drawdown from peak value.`;
    case "loss_streak_cooldown":
      return `Pause new orders for ${formatQuantity(Number(config.cooldown_minutes ?? 0), 0)} minutes after ${formatQuantity(Number(config.loss_streak ?? 0), 0)} consecutive losing trades.`;
    case "per_trade_risk":
      return `Cap loss from entry to stop at ${formatPct(Number(config.max_risk_pct ?? 0))} of the reference account value.`;
    case "market_hours":
      return Boolean(config.enforce_market_hours)
        ? "Market-hours restriction is enabled for new orders."
        : "Optional market-hours restriction.";
    default:
      return fallback || null;
  }
}

function renderField(
  spec: FieldSpec,
  value: FieldValue,
  onChange: (key: string, value: FieldValue) => void
) {
  if (spec.kind === "boolean") {
    return (
      <label key={spec.key} className="space-y-2 text-sm">
        <span className="text-slate-300">{spec.label}</span>
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(spec.key, event.target.checked)}
          className="h-4 w-4 rounded border-border bg-slate-900"
        />
        <div className="text-xs text-slate-400">{spec.help}</div>
      </label>
    );
  }

  return (
    <label key={spec.key} className="space-y-2 text-sm">
      <span className="text-slate-300">{spec.label}</span>
      <input
        type="number"
        min={spec.min}
        step={spec.step}
        value={Number.isFinite(Number(value)) ? Number(value) : 0}
        onChange={(event) => onChange(spec.key, Number(event.target.value))}
        className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100"
      />
      <div className="text-xs text-slate-400">{spec.help}</div>
    </label>
  );
}

export function RiskRuleEditor({ rule, onSaved }: RiskRuleEditorProps) {
  const specs = FIELD_SPECS[rule.rule_type] || [];
  const [enabled, setEnabled] = useState(rule.enabled);
  const [autoClose, setAutoClose] = useState(rule.auto_close);
  const [draftConfig, setDraftConfig] = useState<Record<string, FieldValue>>(() => buildDraftConfig(rule));
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    setEnabled(rule.enabled);
    setAutoClose(rule.auto_close);
    setDraftConfig(buildDraftConfig(rule));
  }, [rule]);

  function updateField(key: string, value: FieldValue) {
    setDraftConfig((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function handleSave() {
    try {
      setSaving(true);
      const normalizedConfig = { ...rule.config_json } as Record<string, unknown>;
      for (const spec of specs) {
        normalizedConfig[spec.key] = normalizeEditorValue(spec, draftConfig[spec.key] ?? 0);
      }

      const saved = await api.saveRiskRule({
        name: rule.name,
        scope: rule.scope,
        rule_type: rule.rule_type,
        enabled,
        auto_close: autoClose,
        description: buildRuleDescription(rule.rule_type, normalizedConfig, rule.description),
        config_json: normalizedConfig,
      });
      onSaved(saved);
      setStatus(`${rule.name} saved.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!specs.length) {
    return null;
  }

  const gridClassName = specs.length === 1 ? "grid gap-4 lg:grid-cols-[auto,auto,1fr]" : "grid gap-4 lg:grid-cols-2";

  return (
    <div className="mt-3 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-3">
      <div className="text-xs uppercase tracking-[0.18em] text-cyan-100">Edit rule</div>
      <div className="mt-3 grid gap-4 lg:grid-cols-[auto,auto]">
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Enabled</span>
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
            className="h-4 w-4 rounded border-border bg-slate-900"
          />
          <div className="text-xs text-slate-400">Turns this risk rule on or off.</div>
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Auto-close</span>
          <input
            type="checkbox"
            checked={autoClose}
            onChange={(event) => setAutoClose(event.target.checked)}
            className="h-4 w-4 rounded border-border bg-slate-900"
          />
          <div className="text-xs text-slate-400">Reserved for future flows that automatically reduce or close risk when a rule is breached.</div>
        </label>
      </div>

      <div className={`mt-4 ${gridClassName}`}>
        {specs.map((spec) => renderField(spec, draftConfig[spec.key] ?? 0, updateField))}
        <div className="flex items-end">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-100 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? "Saving..." : "Save rule"}
          </button>
        </div>
      </div>

      {status ? <div className="mt-3 rounded-xl border border-border px-4 py-2 text-sm text-slate-300">{status}</div> : null}
    </div>
  );
}
