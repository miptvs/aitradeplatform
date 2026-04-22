"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { BrokerAccount } from "@/types";

interface Trading212FormProps {
  account?: BrokerAccount;
  onSaved: (account: BrokerAccount) => void;
}

const DEFAULT_BASE_URL = "https://live.trading212.com/api/v0";

export function Trading212Form({ account, onSaved }: Trading212FormProps) {
  const [enabled, setEnabled] = useState(account?.enabled ?? false);
  const [baseUrl, setBaseUrl] = useState(account?.base_url || DEFAULT_BASE_URL);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);

  useEffect(() => {
    setEnabled(account?.enabled ?? false);
    setBaseUrl(account?.base_url || DEFAULT_BASE_URL);
    setApiKey("");
    setApiSecret("");
  }, [account]);

  async function persistAccount() {
    const saved = await api.saveBrokerAccount({
      name: account?.name || "Trading212 Scaffold",
      broker_type: "trading212",
      mode: "live",
      enabled,
      live_trading_enabled: false,
      base_url: baseUrl,
      api_key: apiKey || null,
      api_secret: apiSecret || null,
      settings_json: account?.settings_json || {
        sync_mode: "manual-mirror",
        supported_actions: ["sync_account", "sync_positions", "sync_orders", "validate_ticker"],
      },
    });
    setApiKey("");
    setApiSecret("");
    onSaved(saved);
    return saved;
  }

  async function handleSave() {
    try {
      setSaving(true);
      await persistAccount();
      setStatus("Trading212 broker settings saved.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleValidate() {
    try {
      setValidating(true);
      const target = await persistAccount();
      const result = await api.validateBrokerAccount(target.id);
      setStatus(result.message);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Validation failed");
    } finally {
      setValidating(false);
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Trading212 ticker validation</div>
          <div className="mt-2 text-lg font-semibold text-slate-100">Backend-only broker credentials</div>
          <div className="mt-1 text-sm text-slate-400">
            Save your Trading212 API key and secret here to validate non-seeded tickers in manual positions. This does not enable live execution.
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Secrets are write-only. Saved values never come back to the frontend. {account?.has_secret ? "A broker secret is currently stored in the backend." : "No broker secret stored in the database yet."}
          </div>
        </div>
        <div className="rounded-full border border-border px-3 py-1 text-xs text-slate-300">
          {account?.status || "not validated"}
        </div>
      </div>

      <div className="mb-4 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-100">
        Trading212 instrument lookup can verify tickers like European ETF symbols that are not part of the initial local asset set. Direct Trading212 order execution remains disabled in this MVP.
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Enable Trading212 lookup</span>
          <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} className="h-4 w-4 rounded border-border bg-slate-900" />
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Base URL</span>
          <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">API key</span>
          <input
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder={account?.has_secret ? "Stored. Enter a new key to replace it." : "Trading212 API key"}
            className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100"
          />
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">API secret</span>
          <input
            type="password"
            value={apiSecret}
            onChange={(event) => setApiSecret(event.target.value)}
            placeholder={account?.has_secret ? "Stored. Enter a new secret to replace it." : "Trading212 API secret"}
            className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100"
          />
        </label>
      </div>

      <div className="mt-4 rounded-xl border border-border bg-black/20 p-3 text-sm text-slate-300">
        <div>What this unlocks:</div>
        <div className="mt-1 text-slate-400">Manual-position ticker search can ask Trading212 to confirm whether a symbol exists and return verified matches instead of treating every unknown ticker as custom.</div>
        <div className="mt-1 text-slate-500">Validate connection saves the current form values first, then tests them against Trading212.</div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleValidate}
          disabled={validating}
          className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {validating ? "Validating..." : "Validate connection"}
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-100 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Saving..." : "Save Trading212 settings"}
        </button>
        {status ? <div className="rounded-xl border border-border px-4 py-2 text-sm text-slate-300">{status}</div> : null}
      </div>
    </div>
  );
}
