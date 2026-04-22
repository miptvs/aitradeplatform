"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ProviderConfig } from "@/types";

interface ProviderFormProps {
  providerType: string;
  provider: ProviderConfig;
  onSaved: (provider: ProviderConfig) => void;
}

export function ProviderForm({ providerType, provider, onSaved }: ProviderFormProps) {
  const [enabled, setEnabled] = useState(provider.enabled);
  const [baseUrl, setBaseUrl] = useState(provider.base_url);
  const [defaultModel, setDefaultModel] = useState(provider.default_model || "");
  const [temperature, setTemperature] = useState(provider.temperature);
  const [maxTokens, setMaxTokens] = useState(provider.max_tokens);
  const [contextWindow, setContextWindow] = useState(provider.context_window);
  const [toolCalling, setToolCalling] = useState(provider.tool_calling_enabled);
  const [reasoningMode, setReasoningMode] = useState(provider.reasoning_mode || "");
  const [apiKey, setApiKey] = useState("");
  const [settingsText, setSettingsText] = useState(JSON.stringify(provider.settings_json, null, 2));
  const [status, setStatus] = useState<string>("");
  const [models, setModels] = useState<string[]>([]);

  useEffect(() => {
    setEnabled(provider.enabled);
    setBaseUrl(provider.base_url);
    setDefaultModel(provider.default_model || "");
    setTemperature(provider.temperature);
    setMaxTokens(provider.max_tokens);
    setContextWindow(provider.context_window);
    setToolCalling(provider.tool_calling_enabled);
    setReasoningMode(provider.reasoning_mode || provider.reasoning_modes[0] || "");
    setApiKey("");
    setSettingsText(JSON.stringify(provider.settings_json, null, 2));
    setStatus("");
    setModels([]);
  }, [provider]);

  async function handleSave() {
    try {
      const saved = await api.saveProviderConfig(providerType, {
        enabled,
        base_url: baseUrl,
        default_model: defaultModel || null,
        temperature,
        max_tokens: maxTokens,
        context_window: contextWindow,
        tool_calling_enabled: toolCalling,
        reasoning_mode: reasoningMode || null,
        api_key: apiKey || null,
        task_defaults: provider.task_defaults,
        settings_json: JSON.parse(settingsText || "{}")
      });
      setApiKey("");
      setStatus("Saved");
      onSaved(saved);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Save failed");
    }
  }

  async function handleTest() {
    try {
      const result = await api.testProvider(providerType);
      setStatus(`${result.status}: ${result.message}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Test failed");
    }
  }

  async function handleModels() {
    try {
      const result = await api.listProviderModels(providerType);
      setModels(result.models);
      setStatus(`Loaded ${result.models.length} models`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Model refresh failed");
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-100">{provider.vendor_name}</div>
          <div className="mt-1 text-lg font-semibold text-slate-100">{provider.mode_label}</div>
          <div className="mt-1 text-xs text-slate-400">
            {provider.description}
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Secrets are write-only. Saved keys never come back to the frontend. {provider.has_secret ? "Secret currently stored." : provider.supports_api_key ? "No secret stored." : "No secret needed for local models."}
          </div>
        </div>
        <div className="text-xs text-slate-400">{provider.last_health_status || "not tested"}</div>
      </div>
      <div className="mb-4 rounded-xl border border-border bg-black/20 p-3">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Suggested models</div>
        <div className="mt-3 flex flex-wrap gap-2">
          {provider.suggested_models.map((model) => (
            <button
              key={model}
              type="button"
              onClick={() => setDefaultModel(model)}
              className={`rounded-full border px-3 py-1 text-xs ${defaultModel === model ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-100" : "border-border text-slate-300 hover:bg-white/5"}`}
            >
              {model}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Enable</span>
          <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} className="h-4 w-4 rounded border-border bg-slate-900" />
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Base URL</span>
          <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Default model</span>
          <input value={defaultModel} onChange={(event) => setDefaultModel(event.target.value)} list={`${providerType}-models`} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          <datalist id={`${providerType}-models`}>
            {[...new Set([...models, ...provider.suggested_models])].map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        </label>
        {provider.supports_api_key ? (
          <label className="space-y-2 text-sm">
            <span className="text-slate-300">API key</span>
            <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={provider.has_secret ? "Stored. Enter new key to replace." : "Required for this remote provider"} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </label>
        ) : (
          <div className="space-y-2 text-sm">
            <span className="text-slate-300">Connection</span>
            <div className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-300">
              Local profile. Point this at your Ollama-compatible endpoint and refresh installed models.
            </div>
          </div>
        )}
        <label className="space-y-2 text-sm">
          <div>
            <span className="text-slate-300">Temperature</span>
            <div className="mt-1 text-xs text-slate-500">
              Controls response randomness. Lower values like 0.0-0.3 are more consistent and conservative, while higher values add more variation. For trading analysis, 0.2 is a sensible default because it keeps outputs steadier and more repeatable.
            </div>
          </div>
          <input type="number" step="0.1" value={temperature} onChange={(event) => setTemperature(Number(event.target.value))} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Max tokens</span>
          <input type="number" value={maxTokens} onChange={(event) => setMaxTokens(Number(event.target.value))} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Context window</span>
          <input type="number" value={contextWindow} onChange={(event) => setContextWindow(Number(event.target.value))} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Reasoning / mode</span>
          {provider.reasoning_modes.length ? (
            <select value={reasoningMode} onChange={(event) => setReasoningMode(event.target.value)} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
              {provider.reasoning_modes.map((mode) => (
                <option key={mode} value={mode}>
                  {mode}
                </option>
              ))}
            </select>
          ) : (
            <input value={reasoningMode} onChange={(event) => setReasoningMode(event.target.value)} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          )}
        </label>
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Tool calling</span>
          <input type="checkbox" checked={toolCalling} onChange={(event) => setToolCalling(event.target.checked)} className="h-4 w-4 rounded border-border bg-slate-900" />
        </label>
      </div>
      <div className="mt-4">
        <label className="space-y-2 text-sm">
          <span className="text-slate-300">Workspace provider settings (JSON)</span>
          <textarea rows={8} value={settingsText} onChange={(event) => setSettingsText(event.target.value)} className="w-full rounded-xl border border-border bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100" />
        </label>
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={handleModels} className="rounded-xl border border-border px-4 py-2 text-sm text-slate-100 hover:bg-white/5">Refresh models</button>
        <button type="button" onClick={handleTest} className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-400/20">Test connection</button>
        <button type="button" onClick={handleSave} className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-100 hover:bg-emerald-400/20">Save provider</button>
        {status ? <div className="rounded-xl border border-border px-4 py-2 text-sm text-slate-300">{status}</div> : null}
      </div>
    </div>
  );
}
