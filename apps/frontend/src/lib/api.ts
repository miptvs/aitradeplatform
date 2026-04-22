import type {
  Alert,
  Asset,
  AssetSearchResponse,
  AutomationDecision,
  AutomationRunResult,
  AnalyticsOverview,
  BrokerAccount,
  BrokerAdapterStatus,
  BrokerSyncResult,
  BrokerValidationResult,
  HealthReadyStatus,
  ExtractedEvent,
  McpStatus,
  NewsArticle,
  NewsRefreshDiagnostics,
  Order,
  PortfolioSnapshot,
  PortfolioSummary,
  Position,
  ProviderConfig,
  ProviderHealth,
  SettingsOverview,
  Signal,
  SignalRefreshResult,
  SimulationAccount,
  SimulationSummary,
  SimulationVsLive,
  StrategyOption,
  TaskMapping,
  TradingAutomationProfile,
  TradingWorkspace,
  Trade
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const text = await response.text();
    let message = text || `Request failed: ${response.status}`;
    try {
      const payload = JSON.parse(text) as { detail?: string; message?: string };
      message = payload.detail || payload.message || message;
    } catch {
      // Ignore JSON parse errors and keep the raw text payload.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getPortfolioSummary: (mode?: string) => request<PortfolioSummary>(`/portfolio/summary${mode ? `?mode=${mode}` : ""}`),
  getPortfolioSnapshots: (mode?: string) => request<PortfolioSnapshot[]>(`/portfolio/snapshots${mode ? `?mode=${mode}` : ""}`),
  getPositions: (params?: { mode?: string; simulationAccountId?: string; brokerAccountId?: string }) => {
    const search = new URLSearchParams();
    if (params?.mode) search.set("mode", params.mode);
    if (params?.simulationAccountId) search.set("simulation_account_id", params.simulationAccountId);
    if (params?.brokerAccountId) search.set("broker_account_id", params.brokerAccountId);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<Position[]>(`/positions${suffix}`);
  },
  createPosition: (payload: Record<string, unknown>) => request<Position>("/positions", { method: "POST", body: JSON.stringify(payload) }),
  updatePosition: (id: string, payload: Record<string, unknown>) => request<Position>(`/positions/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  closePosition: (id: string, options?: { quantity?: number; closePercent?: number; exitPrice?: number }) => {
    const params = new URLSearchParams();
    if (options?.quantity !== undefined) params.set("quantity", String(options.quantity));
    if (options?.closePercent !== undefined) params.set("close_percent", String(options.closePercent));
    if (options?.exitPrice !== undefined) params.set("exit_price", String(options.exitPrice));
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<Position>(`/positions/${id}/close${suffix}`, { method: "POST" });
  },
  getOrders: (params?: { mode?: string; simulationAccountId?: string; brokerAccountId?: string }) => {
    const search = new URLSearchParams();
    if (params?.mode) search.set("mode", params.mode);
    if (params?.simulationAccountId) search.set("simulation_account_id", params.simulationAccountId);
    if (params?.brokerAccountId) search.set("broker_account_id", params.brokerAccountId);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<Order[]>(`/orders${suffix}`);
  },
  createOrder: (payload: Record<string, unknown>) => request<Order>("/orders", { method: "POST", body: JSON.stringify(payload) }),
  getTrades: (params?: { mode?: string; simulationAccountId?: string; brokerAccountId?: string }) => {
    const search = new URLSearchParams();
    if (params?.mode) search.set("mode", params.mode);
    if (params?.simulationAccountId) search.set("simulation_account_id", params.simulationAccountId);
    if (params?.brokerAccountId) search.set("broker_account_id", params.brokerAccountId);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<Trade[]>(`/trades${suffix}`);
  },
  getSignals: (providerType?: string) => request<Signal[]>(`/signals${providerType ? `?provider_type=${encodeURIComponent(providerType)}` : ""}`),
  generateSignals: (providerType: string) =>
    request<SignalRefreshResult>(`/signals/refresh?provider_type=${encodeURIComponent(providerType)}`, { method: "POST" }),
  getNews: () => request<NewsArticle[]>("/news"),
  getNewsDiagnostics: () => request<NewsRefreshDiagnostics>("/news/diagnostics"),
  refreshNews: (payload?: { force_refresh?: boolean; backfill_hours?: number | null }) =>
    request<NewsRefreshDiagnostics>(
      "/news/refresh",
      { method: "POST", body: JSON.stringify(payload || {}) }
    ),
  getEvents: () => request<ExtractedEvent[]>("/events"),
  getStrategies: () => request<StrategyOption[]>("/strategies"),
  getSettingsOverview: () => request<SettingsOverview>("/settings/overview"),
  saveRiskRule: (payload: Record<string, unknown>) => request<{ id: string; name: string; scope: string; rule_type: string; enabled: boolean; auto_close: boolean; description?: string | null; config_json: Record<string, unknown> }>("/risk-rules", { method: "POST", body: JSON.stringify(payload) }),
  saveProviderConfig: (providerType: string, payload: Record<string, unknown>) =>
    request<ProviderConfig>(`/providers/${providerType}`, { method: "POST", body: JSON.stringify(payload) }),
  testProvider: (providerType: string) => request<ProviderHealth>(`/providers/${providerType}/test`, { method: "POST" }),
  listProviderModels: (providerType: string) => request<{ provider_type: string; models: string[] }>(`/providers/${providerType}/models`),
  saveTaskMapping: (payload: TaskMapping) => request<TaskMapping>("/settings/task-mappings", { method: "POST", body: JSON.stringify(payload) }),
  getSimulationAccounts: () => request<SimulationAccount[]>("/simulation/accounts"),
  getSimulationWorkspace: (accountId?: string) => request<TradingWorkspace>(`/simulation/workspace${accountId ? `?account_id=${encodeURIComponent(accountId)}` : ""}`),
  getLiveWorkspace: () => request<TradingWorkspace>("/live/workspace"),
  createSimulationAccount: (payload: Record<string, unknown>) =>
    request<SimulationAccount>("/simulation/accounts", { method: "POST", body: JSON.stringify(payload) }),
  updateSimulationAccount: (id: string, payload: Record<string, unknown>) =>
    request<SimulationAccount>(`/simulation/accounts/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  resetSimulationAccount: (id: string) => request<SimulationAccount>(`/simulation/accounts/${id}/reset`, { method: "POST" }),
  getSimulationSummary: (id: string) => request<SimulationSummary>(`/simulation/accounts/${id}/summary`),
  createSimulationOrder: (payload: Record<string, unknown>) =>
    request<Order>("/simulation/orders", { method: "POST", body: JSON.stringify(payload) }),
  createLiveOrder: (payload: Record<string, unknown>) => request<Order>("/live/orders", { method: "POST", body: JSON.stringify(payload) }),
  updateSimulationStops: (id: string, payload: Record<string, unknown>) =>
    request<Position>(`/simulation/positions/${id}/stops`, { method: "PATCH", body: JSON.stringify(payload) }),
  updateLiveStops: (id: string, payload: Record<string, unknown>) =>
    request<Position>(`/live/positions/${id}/stops`, { method: "PATCH", body: JSON.stringify(payload) }),
  closeSimulationPosition: (id: string, options?: { quantity?: number; closePercent?: number; exitPrice?: number }) => {
    const params = new URLSearchParams();
    if (options?.quantity !== undefined) params.set("quantity", String(options.quantity));
    if (options?.closePercent !== undefined) params.set("close_percent", String(options.closePercent));
    if (options?.exitPrice !== undefined) params.set("exit_price", String(options.exitPrice));
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<Position>(`/simulation/positions/${id}/close${suffix}`, { method: "POST" });
  },
  closeLivePosition: (id: string, options?: { quantity?: number; closePercent?: number; exitPrice?: number }) => {
    const params = new URLSearchParams();
    if (options?.quantity !== undefined) params.set("quantity", String(options.quantity));
    if (options?.closePercent !== undefined) params.set("close_percent", String(options.closePercent));
    if (options?.exitPrice !== undefined) params.set("exit_price", String(options.exitPrice));
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<Position>(`/live/positions/${id}/close${suffix}`, { method: "POST" });
  },
  getSimulationAutomation: () => request<TradingAutomationProfile>("/simulation/automation"),
  saveSimulationAutomation: (payload: Record<string, unknown>) =>
    request<TradingAutomationProfile>("/simulation/automation", { method: "PUT", body: JSON.stringify(payload) }),
  runSimulationAutomation: (accountId?: string) =>
    request<AutomationRunResult>(`/simulation/automation/run${accountId ? `?account_id=${encodeURIComponent(accountId)}` : ""}`, { method: "POST" }),
  rejectSimulationRecommendation: (signalId: string, reason?: string) =>
    request<AutomationDecision>(`/simulation/recommendations/${signalId}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  getLiveAutomation: () => request<TradingAutomationProfile>("/live/automation"),
  saveLiveAutomation: (payload: Record<string, unknown>) =>
    request<TradingAutomationProfile>("/live/automation", { method: "PUT", body: JSON.stringify(payload) }),
  runLiveAutomation: () => request<AutomationRunResult>("/live/automation/run", { method: "POST" }),
  rejectLiveRecommendation: (signalId: string, reason?: string) =>
    request<AutomationDecision>(`/live/recommendations/${signalId}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  syncLiveBroker: (brokerAccountId?: string) =>
    request<BrokerSyncResult>(`/live/broker-sync${brokerAccountId ? `?broker_account_id=${encodeURIComponent(brokerAccountId)}` : ""}`, { method: "POST" }),
  getAnalyticsOverview: () => request<AnalyticsOverview>("/analytics/overview"),
  getEquityCurve: (mode?: string, simulationAccountId?: string) => {
    const params = new URLSearchParams();
    if (mode) params.set("mode", mode);
    if (simulationAccountId) params.set("simulation_account_id", simulationAccountId);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<{ timestamp: string; value: number }[]>(`/analytics/equity-curve${suffix}`);
  },
  getSimulationVsLive: () => request<SimulationVsLive>("/analytics/simulation-vs-live"),
  getAlerts: () => request<Alert[]>("/alerts"),
  getAssets: () => request<Asset[]>("/assets"),
  searchAssets: (query: string) => request<AssetSearchResponse>(`/assets/search?q=${encodeURIComponent(query)}`),
  getBrokerAccounts: () => request<BrokerAccount[]>("/brokers/accounts"),
  getBrokerAdapters: () => request<BrokerAdapterStatus[]>("/brokers/adapters"),
  getMcpStatus: () => request<McpStatus>("/mcp/status"),
  getHealthReady: () => request<HealthReadyStatus>("/health/ready"),
  saveBrokerAccount: (payload: Record<string, unknown>) => request<BrokerAccount>("/brokers/accounts", { method: "POST", body: JSON.stringify(payload) }),
  validateBrokerAccount: (accountId: string) => request<BrokerValidationResult>(`/brokers/accounts/${accountId}/validate`, { method: "POST" }),
  getHealth: () => request<{ status: string; providers: ProviderHealth[]; events: Array<{ component: string; status: string; message: string; observed_at: string }> }>("/health/status")
};
