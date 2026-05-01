"use client";

import { useEffect, useMemo, useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";
import { Bot, CircleAlert, Coins, RefreshCcw, ShieldCheck } from "lucide-react";

import { ProvenanceDialog } from "@/components/provenance/provenance-dialog";
import { PositionManagementTable } from "@/components/trading/position-management-table";
import { SignalTraceDialog } from "@/components/signals/signal-trace-dialog";
import { SignalsTable } from "@/components/signals/signals-table";
import { StatsCard } from "@/components/stats-card";
import { TradesTable } from "@/components/trades/trades-table";
import { Dialog } from "@/components/ui/dialog";
import { HelpTooltip } from "@/components/ui/help-tooltip";
import { RiskBanner } from "@/components/ui/risk-banner";
import { StatusBadge } from "@/components/ui/status-badge";
import { useWorkspace } from "@/components/layout/workspace-provider";
import { useApi } from "@/hooks/use-api";
import { useProvenanceTrace } from "@/hooks/use-provenance-trace";
import { api } from "@/lib/api";
import { formatCurrency, formatDateTime, formatPct, formatQuantity } from "@/lib/utils";
import type {
  Asset,
  AssetSearchResult,
  Order,
  Position,
  ReplayRun,
  Signal,
  SignalTrace,
  Trade,
  TradingAutomationProfile,
  TradingRecommendation,
  TradingWorkspace as TradingWorkspaceData,
} from "@/types";

type TradingMode = "live" | "simulation";
type SizingMode = "amount" | "quantity";

const RISK_PRESETS = {
  conservative: { stopLossPct: 0.02, takeProfitPct: 0.04, trailingStopPct: 0.015 },
  balanced: { stopLossPct: 0.03, takeProfitPct: 0.06, trailingStopPct: 0.02 },
  aggressive: { stopLossPct: 0.05, takeProfitPct: 0.1, trailingStopPct: 0.03 },
} as const;

const TRADE_ACTIONS = [
  { value: "buy", label: "Buy / open long", help: "Uses cash to buy or add to a long position." },
  { value: "sell", label: "Sell / reduce long", help: "Sells existing long holdings. Live shorting is not assumed." },
  { value: "close_long", label: "Close long", help: "Exit an existing long position." },
  { value: "reduce_long", label: "Reduce long", help: "Trim part of an existing long position." },
  { value: "short", label: "Short (simulation)", help: "Open a simulated short if short simulation is enabled." },
  { value: "cover_short", label: "Cover short", help: "Close or reduce an existing simulated short." },
] as const;

export function TradingWorkspace({
  mode,
  title,
  description,
}: {
  mode: TradingMode;
  title: string;
  description: string;
}) {
  const workspace = useWorkspace();
  const [automationOpen, setAutomationOpen] = useState(false);
  const [replayOpen, setReplayOpen] = useState(mode === "simulation");
  const [manualTradingOpen, setManualTradingOpen] = useState(false);
  const [selectedSimulationAccountId, setSelectedSimulationAccountId] = useState("");
  const workspaceState = useApi<TradingWorkspaceData>(
    () => (mode === "live" ? api.getLiveWorkspace() : api.getSimulationWorkspace(selectedSimulationAccountId || undefined)),
    [mode, selectedSimulationAccountId]
  );
  const replayRunsState = useApi<ReplayRun[]>(
    () => (mode === "simulation" ? api.getReplayRuns() : Promise.resolve([])),
    [mode]
  );

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<AssetSearchResult[]>([]);
  const [searchMessage, setSearchMessage] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [banner, setBanner] = useState<{ tone: "success" | "warn" | "error"; message: string } | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [manualPositionOpen, setManualPositionOpen] = useState(false);
  const [stopDialogPosition, setStopDialogPosition] = useState<Position | null>(null);
  const [closeDialogPosition, setCloseDialogPosition] = useState<Position | null>(null);
  const [detailPosition, setDetailPosition] = useState<Position | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [signalTrace, setSignalTrace] = useState<SignalTrace | null>(null);
  const [signalTraceLoading, setSignalTraceLoading] = useState(false);
  const [signalTraceError, setSignalTraceError] = useState<string | null>(null);
  const [signalApproveBusy, setSignalApproveBusy] = useState(false);

  const [orderForm, setOrderForm] = useState({
    asset_id: "",
    asset_symbol: "",
    asset_name: "",
    asset_type: "stock",
    currency: "USD",
    exchange: "",
    side: "buy",
    order_type: "market",
    sizing_mode: "amount" as SizingMode,
    amount: "100",
    quantity: "",
    requested_price: "",
    stop_loss: "",
    take_profit: "",
    trailing_stop: "",
    strategy_name: "trend-following",
    provider_type: mode === "simulation" ? workspace.simulationProviderType : workspace.liveProviderType,
    model_name: "",
    risk_profile: "balanced",
    notes: "Manual order review",
    signal_id: "",
  });
  const [manualPositionForm, setManualPositionForm] = useState({
    asset_id: "",
    asset_symbol: "",
    asset_name: "",
    asset_type: "stock",
    currency: "USD",
    exchange: "",
    sizing_mode: "amount" as SizingMode,
    amount: "100",
    quantity: "",
    avg_entry_price: "",
    current_price: "",
    stop_loss: "",
    take_profit: "",
    trailing_stop: "",
    notes: "",
  });
  const [stopForm, setStopForm] = useState({ stop_loss: "", take_profit: "", trailing_stop: "", notes: "" });
  const [closePercent, setClosePercent] = useState("");
  const [automationForm, setAutomationForm] = useState<TradingAutomationProfile | null>(null);
  const [replayForm, setReplayForm] = useState({
    date_start: "",
    date_end: "",
    starting_cash: "10000",
    selected_models: [] as string[],
    symbols: [] as string[],
    fees_bps: "5",
    slippage_bps: "2",
    cash_reserve_percent: "20",
    short_enabled: false,
    enforce_market_hours: false,
  });
  const [recommendationBusyId, setRecommendationBusyId] = useState<string | null>(null);
  const [brokerSyncingId, setBrokerSyncingId] = useState<string | null>(null);
  const [clearRiskBusy, setClearRiskBusy] = useState(false);
  const provenance = useProvenanceTrace();

  const workspaceData = workspaceState.data;
  const simulationAccounts = ((workspaceData?.controls.simulation_accounts as Array<Record<string, unknown>> | undefined) || []);
  const brokerAccounts = ((workspaceData?.controls.broker_accounts as Array<Record<string, unknown>> | undefined) || []);
  const localAssetDefaults = useMemo(() => (workspaceData?.assets || []).slice(0, 8).map(toLocalSearchResult), [workspaceData?.assets]);
  const providerOptions = useMemo(
    () => {
      const simulationAccountProviders = ((workspaceData?.controls.simulation_accounts as Array<Record<string, unknown>> | undefined) || [])
        .map((account) => String(account.provider_type || ""))
        .filter(Boolean);
      const liveModelProvider = String(workspaceData?.controls.live_model_provider_type || "");
      return Array.from(
        new Set([
          mode === "simulation" ? workspace.simulationProviderType : liveModelProvider || workspace.liveProviderType,
          workspace.signalProviderType,
          ...simulationAccountProviders,
          "manual",
        ].filter(Boolean))
      );
    },
    [mode, workspace.liveProviderType, workspace.signalProviderType, workspace.simulationProviderType, workspaceData?.controls]
  );

  useEffect(() => {
    if (mode !== "simulation" || !workspaceData) return;
    const controlAccountId = String((workspaceData.controls.active_simulation_account_id as string | undefined) || "");
    const simulationAccounts = (workspaceData.controls.simulation_accounts as Array<Record<string, unknown>> | undefined) || [];
    const workspaceAccount = simulationAccounts.find(
      (account) => String(account.provider_type || "") === workspace.simulationProviderType
    );
    const preferredAccountId = String(workspaceAccount?.id || controlAccountId || "");
    if (preferredAccountId && !selectedSimulationAccountId) {
      setSelectedSimulationAccountId(preferredAccountId);
    }
    const modelDefaults = simulationAccounts.map((account) => String(account.provider_type || "")).filter(Boolean).slice(0, 4);
    const symbolDefaults = (workspaceData.assets || []).map((asset) => asset.symbol).slice(0, 5);
    setReplayForm((current) => ({
      ...current,
      selected_models: current.selected_models.length ? current.selected_models : modelDefaults,
      symbols: current.symbols.length ? current.symbols : symbolDefaults,
      date_start: current.date_start || defaultReplayStart(),
      date_end: current.date_end || defaultReplayEnd(),
    }));
  }, [mode, selectedSimulationAccountId, workspace.simulationProviderType, workspaceData]);

  useEffect(() => {
    if (!workspaceData) return;
    setAutomationForm(workspaceData.automation);
  }, [workspaceData]);

  const selectedAsset = useMemo(() => {
    if (!workspaceData) return null;
    if (orderForm.asset_id) {
      return workspaceData.assets.find((asset) => asset.id === orderForm.asset_id) || null;
    }
    return workspaceData.assets.find((asset) => asset.symbol === orderForm.asset_symbol) || null;
  }, [orderForm.asset_id, orderForm.asset_symbol, workspaceData]);

  useEffect(() => {
    const normalized = normalizeSymbol(searchQuery);
    if (!normalized) {
      setSearchResults(localAssetDefaults);
      setSearchMessage("Showing recently used assets in this workspace.");
      setSearchLoading(false);
      return;
    }

    let active = true;
    setSearchLoading(true);
    const timer = window.setTimeout(() => {
      api
        .searchAssets(normalized)
        .then((response) => {
          if (!active) return;
          setSearchResults(response.results);
          setSearchMessage(response.message || "");
        })
        .catch((error) => {
          if (!active) return;
          setSearchResults([]);
          setSearchMessage(error instanceof Error ? error.message : "Ticker search failed.");
        })
        .finally(() => {
          if (active) setSearchLoading(false);
        });
    }, 220);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [localAssetDefaults, searchQuery]);

  useEffect(() => {
    if (!selectedAsset) return;
    setOrderForm((current) => ({
      ...current,
      asset_symbol: selectedAsset.symbol,
      asset_name: selectedAsset.name,
      asset_type: selectedAsset.asset_type,
      currency: selectedAsset.currency,
      exchange: selectedAsset.exchange || "",
      requested_price: current.requested_price || (selectedAsset.latest_price ? String(selectedAsset.latest_price) : ""),
    }));
    setManualPositionForm((current) => ({
      ...current,
      asset_id: selectedAsset.id,
      asset_symbol: selectedAsset.symbol,
      asset_name: selectedAsset.name,
      asset_type: selectedAsset.asset_type,
      currency: selectedAsset.currency,
      exchange: selectedAsset.exchange || "",
      avg_entry_price: current.avg_entry_price || (selectedAsset.latest_price ? String(selectedAsset.latest_price) : ""),
      current_price: current.current_price || (selectedAsset.latest_price ? String(selectedAsset.latest_price) : ""),
    }));
  }, [selectedAsset]);

  useEffect(() => {
    const preset = RISK_PRESETS[orderForm.risk_profile as keyof typeof RISK_PRESETS];
    const entry = Number(orderForm.requested_price || selectedAsset?.latest_price || 0);
    if (!preset || !(entry > 0)) return;
    setOrderForm((current) => ({
      ...current,
      stop_loss: current.stop_loss || String(round(entry * (1 - preset.stopLossPct))),
      take_profit: current.take_profit || String(round(entry * (1 + preset.takeProfitPct))),
      trailing_stop: current.trailing_stop || String(round(entry * preset.trailingStopPct)),
    }));
  }, [orderForm.requested_price, orderForm.risk_profile, selectedAsset?.latest_price]);

  if (workspaceState.loading || !workspaceData || !automationForm) {
    return <div className="text-sm text-slate-400">Loading {title.toLowerCase()}...</div>;
  }
  if (workspaceState.error) {
    return <div className="text-sm text-rose-300">{title} failed to load: {workspaceState.error}</div>;
  }

  const activeSignals = workspaceData.signals.slice(0, 8);
  const currentCurrency = orderForm.currency || selectedAsset?.currency || workspaceData.account.base_currency || "USD";
  const requestedPrice = Number(orderForm.requested_price || selectedAsset?.latest_price || 0);
  const derivedQuantity = orderForm.sizing_mode === "amount" ? deriveQuantity(orderForm.amount, requestedPrice) : Number(orderForm.quantity || 0);
  const orderNotional = requestedPrice > 0 ? derivedQuantity * requestedPrice : 0;
  const openPositions = workspaceData.positions.filter((position) => position.status === "open");
  const closedPositions = workspaceData.positions.filter((position) => position.status === "closed");
  const closePreviewPct = closePercent ? Number(closePercent) : 100;
  const closePreviewQty = closeDialogPosition ? (Math.abs(closeDialogPosition.quantity) * closePreviewPct) / 100 : 0;

  function loadRecommendationIntoTicket(recommendation: TradingRecommendation) {
    if (!workspaceData || !automationForm) return;
    const asset = workspaceData.assets.find((item) => item.id === recommendation.asset_id);
    const suggestedEntry = recommendation.suggested_entry || asset?.latest_price || 0;
    const trailingStop =
      automationForm.trailing_stop_pct && suggestedEntry > 0 ? String(round(suggestedEntry * automationForm.trailing_stop_pct)) : "";
    const cappedNotional = Math.max(
      0,
      Math.min(
        automationForm.default_order_notional,
        Number(workspaceData.account.available_to_trade_cash || automationForm.default_order_notional)
      )
    );
    const derivedQuantityFromNotional =
      cappedNotional > 0 && suggestedEntry > 0
        ? String(Math.round((cappedNotional / suggestedEntry) * 1_000_000) / 1_000_000)
        : "";

    setOrderForm((current) => ({
      ...current,
      asset_id: recommendation.asset_id,
      asset_symbol: recommendation.symbol,
      asset_name: recommendation.asset_name,
      asset_type: asset?.asset_type || current.asset_type,
      currency: asset?.currency || current.currency,
      exchange: asset?.exchange || "",
      side: recommendation.action,
      order_type: "market",
      sizing_mode: "amount",
      amount: String(cappedNotional),
      quantity: derivedQuantityFromNotional,
      requested_price: suggestedEntry ? String(suggestedEntry) : current.requested_price,
      stop_loss: recommendation.suggested_stop_loss ? String(recommendation.suggested_stop_loss) : current.stop_loss,
      take_profit: recommendation.suggested_take_profit ? String(recommendation.suggested_take_profit) : current.take_profit,
      trailing_stop: trailingStop || current.trailing_stop,
      strategy_name: recommendation.strategy_slug || current.strategy_name,
      provider_type: recommendation.provider_type || current.provider_type,
      model_name: recommendation.model_name || current.model_name,
      notes: `Manual approval from queue. ${recommendation.reason}`.trim(),
      signal_id: recommendation.signal_id,
    }));
    setSearchQuery(recommendation.symbol);
    setReviewOpen(true);
    setBanner({
      tone: "success",
      message: `${recommendation.symbol} was loaded into the review ticket. Confirm sizing and stops before sending it.`,
    });
  }

  async function handleRejectRecommendation(recommendation: TradingRecommendation) {
    try {
      setRecommendationBusyId(recommendation.signal_id);
      if (mode === "live") {
        await api.rejectLiveRecommendation(recommendation.signal_id, "Rejected from the approval queue by the operator.");
      } else {
        await api.rejectSimulationRecommendation(recommendation.signal_id, "Rejected from the approval queue by the operator.");
      }
      setBanner({ tone: "warn", message: `${recommendation.symbol} was rejected and removed from the approval queue.` });
      workspaceState.reload();
    } catch (error) {
      setBanner({ tone: "error", message: error instanceof Error ? error.message : "Recommendation rejection failed." });
    } finally {
      setRecommendationBusyId(null);
    }
  }

  async function handleSyncLiveBroker(brokerAccountId?: string) {
    if (!brokerAccountId) return;
    try {
      setBrokerSyncingId(brokerAccountId);
      const result = await api.syncLiveBroker(brokerAccountId);
      setBanner({
        tone: result.status === "ok" ? "success" : result.status === "warn" ? "warn" : "error",
        message: `${result.message} Account: ${result.account_message} Positions: ${result.positions_message} Pies: ${result.pies_message || "not checked"} Orders: ${result.orders_message}`,
      });
      workspaceState.reload();
    } catch (error) {
      setBanner({ tone: "error", message: error instanceof Error ? error.message : "Broker sync failed." });
    } finally {
      setBrokerSyncingId(null);
    }
  }

  async function handleOpenSignal(signal: Signal) {
    setSelectedSignal(signal);
    setSignalTraceLoading(true);
    setSignalTraceError(null);
    try {
      const trace = await api.getSignalTrace(signal.id);
      setSignalTrace(trace);
    } catch (error) {
      setSignalTrace(null);
      setSignalTraceError(error instanceof Error ? error.message : "Signal trace failed to load.");
    } finally {
      setSignalTraceLoading(false);
    }
  }

  async function handleApproveCurrentSignal() {
    if (!selectedSignal) return;
    try {
      setSignalApproveBusy(true);
      const decision =
        mode === "live"
          ? await api.approveLiveSignal(selectedSignal.id)
          : await api.approveSimulationSignal(selectedSignal.id);
      setBanner({
        tone: "success",
        message: decision.reason,
      });
      await handleOpenSignal(selectedSignal);
      workspaceState.reload();
    } catch (error) {
      setSignalTraceError(error instanceof Error ? error.message : "Signal approval failed.");
    } finally {
      setSignalApproveBusy(false);
    }
  }

  async function handleClearRiskNotices() {
    try {
      setClearRiskBusy(true);
      const result = await api.clearAlerts({ mode, includeSystem: true, warningOnly: true });
      setBanner({
        tone: "success",
        message: result.resolved
          ? `Cleaned up ${result.resolved} ${mode} warning notice${result.resolved === 1 ? "" : "s"}.`
          : "No open warning notices needed cleanup.",
      });
      workspaceState.reload();
    } catch (error) {
      setBanner({
        tone: "error",
        message: error instanceof Error ? error.message : "Risk notice cleanup failed.",
      });
    } finally {
      setClearRiskBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{mode === "live" ? "Live Trading" : "Simulation"}</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100">{title}</h1>
          <div className="mt-2 text-sm text-slate-400">{description}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => workspaceState.reload()}
            className="inline-flex items-center gap-2 rounded-xl border border-border px-3 py-2 text-sm text-slate-200 hover:bg-white/5"
            title="Refresh account, positions, orders, signals, and alerts for this workspace."
          >
            <RefreshCcw size={15} />
            Refresh
          </button>
        </div>
      </div>

      {banner ? <Banner tone={banner.tone} message={banner.message} /> : null}
      <RiskBanner alerts={workspaceData.alerts} mode={mode} onClear={handleClearRiskNotices} clearBusy={clearRiskBusy} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatsCard label="Account Value" value={workspaceData.account.total_value} />
        <StatsCard label="Total Cash" value={workspaceData.account.total_cash ?? workspaceData.account.cash_available} />
        <StatsCard label="Available To Trade" value={workspaceData.account.available_to_trade_cash ?? workspaceData.account.cash_available} />
        <StatsCard label="Equity" value={workspaceData.account.equity} />
        <StatsCard label="Realized PnL" value={workspaceData.account.realized_pnl} />
        <StatsCard label="Unrealized PnL" value={workspaceData.account.unrealized_pnl} />
      </div>

      <div className="space-y-4">
        <AccountSummaryPanel
          mode={mode}
          workspaceData={workspaceData}
          simulationAccounts={simulationAccounts}
          brokerAccounts={brokerAccounts}
          brokerSyncingId={brokerSyncingId}
          selectedSimulationAccountId={selectedSimulationAccountId}
          onChangeSimulationAccount={setSelectedSimulationAccountId}
          onResetSimulation={async () => {
            if (!selectedSimulationAccountId) return;
            if (!window.confirm("Reset this simulation account back to its configured starting balance?")) return;
            await api.resetSimulationAccount(selectedSimulationAccountId);
            setBanner({ tone: "success", message: "Simulation account reset. Cash, positions, orders, trades, and snapshots for this account were cleaned." });
            workspaceState.reload();
          }}
          onSaveSimulationSettings={async (payload) => {
            if (!selectedSimulationAccountId) return;
            await api.updateSimulationAccount(selectedSimulationAccountId, payload);
            setBanner({ tone: "success", message: "Simulation account settings saved." });
            workspaceState.reload();
          }}
          onSyncLiveBroker={handleSyncLiveBroker}
        />

        {mode === "simulation" ? (
          <ReplayBacktestPanel
            open={replayOpen}
            onToggle={() => setReplayOpen((current) => !current)}
            workspaceData={workspaceData}
            simulationAccounts={simulationAccounts}
            replayRuns={replayRunsState.data || []}
            loading={replayRunsState.loading}
            form={replayForm}
            onChange={setReplayForm}
            onCreate={async () => {
              try {
                const run = await api.createReplayRun({
                  date_start: new Date(replayForm.date_start).toISOString(),
                  date_end: new Date(replayForm.date_end).toISOString(),
                  starting_cash: Number(replayForm.starting_cash || 0),
                  selected_models: replayForm.selected_models,
                  symbols: replayForm.symbols,
                  fees_bps: Number(replayForm.fees_bps || 0),
                  slippage_bps: Number(replayForm.slippage_bps || 0),
                  cash_reserve_percent: Math.max(0, Number(replayForm.cash_reserve_percent || 0)) / 100,
                  short_enabled: replayForm.short_enabled,
                  config_json: { enforce_market_hours: replayForm.enforce_market_hours },
                });
                setBanner({ tone: "success", message: `${run.name} completed for ${run.results.length} model result${run.results.length === 1 ? "" : "s"}.` });
                replayRunsState.reload();
              } catch (error) {
                setBanner({ tone: "error", message: error instanceof Error ? error.message : "Replay run failed." });
              }
            }}
          />
        ) : null}

        <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <button
              type="button"
              onClick={() => setManualTradingOpen((current) => !current)}
              className="flex-1 text-left"
              title="Open or close the manual order ticket for this account."
            >
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Manual trading controls</div>
              <div className="mt-1 text-sm text-slate-400">
                Manual order entry sits directly under the account it affects. Use it for buy/sell tickets, stop levels, and guarded review before submit.
              </div>
              <div className="mt-2 text-xs text-slate-500">
                Current draft: {orderForm.side.toUpperCase()} {orderForm.asset_symbol || "no symbol selected"} ·{" "}
                {orderForm.sizing_mode === "amount" ? formatCurrency(Number(orderForm.amount || 0), currentCurrency) : `${orderForm.quantity || 0} qty`}
              </div>
            </button>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={mode === "live" ? "live" : "simulation"} />
              <button
                type="button"
                onClick={() => setManualPositionOpen(true)}
                className="rounded-xl border border-border px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/5"
                title="Records a position that already exists in your broker or outside this order ticket so this workspace can manage stops and reporting."
              >
                Add existing position
              </button>
              <button
                type="button"
                onClick={() => setManualTradingOpen((current) => !current)}
                className="rounded-full border border-border px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-200 hover:bg-white/5"
              >
                {manualTradingOpen ? "Close" : "Open"}
              </button>
            </div>
          </div>
          {manualTradingOpen ? (
            <div className="mt-4">
              <OrderEntryPanel
                mode={mode}
                workspaceData={workspaceData}
                providerOptions={providerOptions}
                searchQuery={searchQuery}
                searchLoading={searchLoading}
                searchMessage={searchMessage}
                searchResults={searchResults}
                orderForm={orderForm}
                selectedAsset={selectedAsset}
                currentCurrency={currentCurrency}
                derivedQuantity={derivedQuantity}
                orderNotional={orderNotional}
                embedded
                onSearchQueryChange={setSearchQuery}
                onChooseAsset={(asset) => {
                  setOrderForm((current) => ({
                    ...current,
                    asset_id: asset.asset_id || "",
                    asset_symbol: asset.symbol,
                    asset_name: asset.name,
                    asset_type: asset.asset_type,
                    currency: asset.currency,
                    exchange: asset.exchange || "",
                  }));
                  setManualPositionForm((current) => ({
                    ...current,
                    asset_id: asset.asset_id || "",
                    asset_symbol: asset.symbol,
                    asset_name: asset.name,
                    asset_type: asset.asset_type,
                    currency: asset.currency,
                    exchange: asset.exchange || "",
                  }));
                  setSearchQuery(asset.symbol);
                }}
                onChange={setOrderForm}
                onOpenExistingPosition={() => setManualPositionOpen(true)}
                onOpenReview={() => setReviewOpen(true)}
              />
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-border bg-black/20 p-4 text-sm text-slate-300">
              Open this drawer to create a manual {mode} order. Every ticket still goes through review and risk validation before it can affect the account.
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <button
            type="button"
            onClick={() => setAutomationOpen((current) => !current)}
            className="flex w-full flex-col gap-3 text-left md:flex-row md:items-center md:justify-between"
            title="Open or close automation settings for this account."
          >
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Automation controls</div>
              <div className="mt-1 text-sm text-slate-400">
                Account-level automation settings live here, directly under the manual ticket they can load or execute.
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={automationForm.automation_enabled ? "enabled" : "disabled"} />
              <span className="rounded-full border border-border px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-200">
                {automationOpen ? "Close" : "Open"}
              </span>
            </div>
          </button>
          {automationOpen ? (
            <div className="mt-4">
              <AutomationControlPanel
                mode={mode}
                workspaceData={workspaceData}
                providerOptions={providerOptions}
                automationForm={automationForm}
                embedded
                onChange={setAutomationForm}
                onSave={async () => {
                  const saver = mode === "live" ? api.saveLiveAutomation : api.saveSimulationAutomation;
                  const next = await saver({ ...automationForm });
                  setAutomationForm(next);
                  setBanner({ tone: "success", message: "Automation controls saved for this workspace." });
                  workspaceState.reload();
                }}
                onRun={async () => {
                  const result =
                    mode === "live"
                      ? await api.runLiveAutomation()
                      : await api.runSimulationAutomation(selectedSimulationAccountId || undefined);
                  setBanner({
                    tone: result.status === "success" ? "success" : result.status === "blocked" ? "warn" : "error",
                    message: `${result.message} Processed ${result.processed_signals} signal(s).`,
                  });
                  workspaceState.reload();
                }}
              />
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-border bg-black/20 p-4 text-sm text-slate-300">
              {automationForm.automation_enabled
                ? `${automationForm.approval_mode.replace("_", " ")} is enabled at ${formatPct(automationForm.confidence_threshold)} confidence. ${
                    automationForm.scheduled_execution_enabled
                      ? `Scheduled checks run every ${formatInterval(automationForm.execution_interval_seconds)}.`
                      : "Scheduled checks are off."
                  }`
                : "Automation is currently disabled. Open this drawer to configure or run it."}
            </div>
          )}
        </section>
      </div>

      <div className="space-y-4">
        <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Open {mode} positions</div>
              <div className="mt-1 text-sm text-slate-400">The action menu keeps stop management compact while still exposing manual overrides, partial closes, and details.</div>
            </div>
          </div>
          <PositionManagementTable
            positions={openPositions}
            emptyMessage={`No ${mode} positions yet. Use the order ticket or record an existing fill to get started.`}
            onViewDetails={setDetailPosition}
            onEditStops={(position) => {
              setStopDialogPosition(position);
              setStopForm({
                stop_loss: position.stop_loss ? String(position.stop_loss) : "",
                take_profit: position.take_profit ? String(position.take_profit) : "",
                trailing_stop: position.trailing_stop ? String(position.trailing_stop) : "",
                notes: position.notes || "",
              });
            }}
            onClose={(position) => {
              setCloseDialogPosition(position);
              setClosePercent("");
            }}
            onMarkOverride={async (position) => {
              await api.updatePosition(position.id, { manual_override: true });
              setBanner({ tone: "success", message: `${position.symbol} is now marked as a manual override.` });
              workspaceState.reload();
            }}
            onViewTrace={(position) => provenance.openTrace({ type: "position", id: position.id })}
          />
          <section className="mt-4 rounded-2xl border border-border bg-black/20 p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Closed {mode} positions</div>
                <div className="mt-1 text-sm text-slate-400">Closed lines stay visible for review until you clean them from the active workspace view.</div>
              </div>
              <button
                type="button"
                disabled={!closedPositions.length}
                onClick={async () => {
                  const result =
                    mode === "live"
                      ? await api.cleanLiveClosedPositions()
                      : await api.cleanSimulationClosedPositions(selectedSimulationAccountId || undefined);
                  setBanner({ tone: "success", message: `${result.archived} closed position${result.archived === 1 ? "" : "s"} cleaned from this workspace.` });
                  workspaceState.reload();
                }}
                className="rounded-xl border border-border px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-200 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Clean closed
              </button>
            </div>
            <div className="mt-4">
              <PositionManagementTable
                positions={closedPositions}
                emptyMessage={`No closed ${mode} positions to review.`}
                onViewDetails={setDetailPosition}
                onEditStops={setStopDialogPosition}
                onClose={setCloseDialogPosition}
                onMarkOverride={async (position) => {
                  await api.updatePosition(position.id, { manual_override: true });
                  setBanner({ tone: "success", message: `${position.symbol} is now marked as a manual override.` });
                  workspaceState.reload();
                }}
                onViewTrace={(position) => provenance.openTrace({ type: "position", id: position.id })}
              />
            </div>
          </section>
          <section className="mt-4 rounded-2xl border border-border bg-black/20 p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Signals available here</div>
                <div className="mt-1 text-sm text-slate-400">These signal candidates feed both live and simulation. Open any signal to inspect its news, rationale, lane status, and full review-to-execution trace.</div>
              </div>
              <StatusBadge status={workspaceData.account.status} />
            </div>
            <div className="mt-4">
              <SignalsTable signals={activeSignals} onSelectSignal={handleOpenSignal} />
            </div>
          </section>
        </section>

        <RecommendationQueue
          mode={mode}
          recommendations={workspaceData.recommendations}
          busySignalId={recommendationBusyId}
          onLoadTicket={loadRecommendationIntoTicket}
          onReject={handleRejectRecommendation}
        />

        <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Safety and broker state</div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <InfoRow icon={<ShieldCheck size={15} />} label="Safety state" value={workspaceData.account.safety_message} />
            <InfoRow icon={<Coins size={15} />} label="Active account" value={workspaceData.account.account_label} />
            <InfoRow
              icon={<Bot size={15} />}
              label="Automation"
              value={
                automationForm.automation_enabled
                  ? `${automationForm.approval_mode.replace("_", " ")} · threshold ${formatPct(automationForm.confidence_threshold)}`
                  : "Disabled"
              }
            />
            <InfoRow
              icon={<ShieldCheck size={15} />}
              label="Settings source"
              value={
                mode === "simulation" && automationForm.inherit_from_live
                  ? "Simulation inherits live strategy, provider, and risk policy unless overridden"
                  : "Workspace-specific strategy, provider, and risk policy"
              }
            />
            <InfoRow
              icon={<Bot size={15} />}
              label="Provider / threshold"
              value={`${
                automationForm.allowed_provider_types.length
                  ? automationForm.allowed_provider_types.join(", ")
                  : mode === "simulation"
                    ? workspace.simulationProviderType
                    : workspace.liveProviderType
              } · ${formatPct(automationForm.confidence_threshold)}`}
            />
            <InfoRow
              icon={<CircleAlert size={15} />}
              label="Execution"
              value={String(workspaceData.account.metadata.supports_execution || false) === "true" ? "Broker can execute" : "Scaffold / guarded path"}
            />
          </div>
        </section>
      </div>

      <ExecutionHistoryPanel
        mode={mode}
        orders={workspaceData.orders}
        trades={workspaceData.trades}
        onViewTrace={(type, item) => provenance.openTrace({ type, id: item.id })}
      />

      <Dialog
        open={reviewOpen}
        title="Review order before submit"
        description="Manual and automatic orders both pass through the same risk engine. This review step helps you confirm the exact sizing, protective levels, and execution lane."
        actions={
          <button type="button" onClick={() => setReviewOpen(false)} className="rounded-xl border border-border px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
            Close
          </button>
        }
      >
        <div className="grid gap-4 md:grid-cols-2">
          <ReviewStat label="Symbol" value={orderForm.asset_symbol || "-"} />
          <ReviewStat label="Side / Type" value={`${orderForm.side.toUpperCase()} · ${orderForm.order_type}`} />
          <ReviewStat label="Quantity" value={formatQuantity(derivedQuantity, 6)} />
          <ReviewStat label="Estimated Notional" value={formatCurrency(orderNotional, currentCurrency)} />
          <ReviewStat label="Entry" value={formatCurrency(requestedPrice || 0, currentCurrency)} />
          <ReviewStat label="Stop / Target" value={`${orderForm.stop_loss || "-"} / ${orderForm.take_profit || "-"}`} />
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={async () => {
              try {
                const buyLike = ["buy", "short"].includes(orderForm.side);
                const availableToTrade = Number(workspaceData.account.available_to_trade_cash || 0);
                if (buyLike && orderNotional > availableToTrade) {
                  setBanner({
                    tone: "warn",
                    message:
                      availableToTrade <= 0
                        ? "Order not processed because the cash reserve rule leaves no available-to-trade cash. Insufficient balance checks still apply to submitted orders."
                        : `Order not processed because it would breach the cash reserve. Available to trade is ${formatCurrency(availableToTrade, currentCurrency)}.`,
                  });
                  return;
                }
                const basePayload = {
                  asset_id: orderForm.asset_id,
                  side: orderForm.side,
                  order_type: orderForm.order_type,
                  quantity: orderForm.sizing_mode === "quantity" ? Number(orderForm.quantity) : null,
                  amount: orderForm.sizing_mode === "amount" ? Number(orderForm.amount) : null,
                  requested_price: orderForm.requested_price ? Number(orderForm.requested_price) : null,
                  stop_loss: parseOptional(orderForm.stop_loss),
                  take_profit: parseOptional(orderForm.take_profit),
                  trailing_stop: parseOptional(orderForm.trailing_stop),
                  strategy_name: orderForm.strategy_name,
                  provider_type: orderForm.provider_type === "manual" ? null : orderForm.provider_type,
                  model_name: orderForm.model_name || null,
                  manual: true,
                  entry_reason: orderForm.notes,
                  signal_id: orderForm.signal_id || null,
                };
                const order =
                  mode === "live"
                    ? await api.createLiveOrder(basePayload)
                    : await api.createSimulationOrder({
                        ...basePayload,
                        simulation_account_id: selectedSimulationAccountId,
                        reason: orderForm.notes,
                      });
                setBanner({
                  tone: order.status === "rejected" ? "warn" : "success",
                  message: order.rejection_reason || `Order ${order.status} for ${order.symbol}.`,
                });
                setReviewOpen(false);
                workspaceState.reload();
              } catch (error) {
                setBanner({ tone: "error", message: error instanceof Error ? error.message : "Order submission failed." });
              }
            }}
            className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 hover:bg-emerald-500/20"
          >
            Submit order
          </button>
          <button type="button" onClick={() => setReviewOpen(false)} className="rounded-xl border border-border px-4 py-2 text-sm text-slate-300 hover:bg-white/5">
            Keep editing
          </button>
        </div>
      </Dialog>

      <Dialog
        open={manualPositionOpen}
        title="Add existing position"
        description="Use this when the trade already exists in your broker or outside this ticket and you want the workspace to start tracking it. This records the position for monitoring, stops, and parity. It does not place a new order."
        actions={
          <button type="button" onClick={() => setManualPositionOpen(false)} className="rounded-xl border border-border px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
            Close
          </button>
        }
      >
        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            try {
              const payload = {
                asset_id: manualPositionForm.asset_id || null,
                asset_symbol: manualPositionForm.asset_symbol,
                asset_name: manualPositionForm.asset_name,
                asset_type: manualPositionForm.asset_type,
                currency: manualPositionForm.currency,
                exchange: manualPositionForm.exchange || null,
                mode,
                quantity:
                  manualPositionForm.sizing_mode === "quantity"
                    ? Number(manualPositionForm.quantity)
                    : deriveQuantity(manualPositionForm.amount, Number(manualPositionForm.avg_entry_price)),
                avg_entry_price: Number(manualPositionForm.avg_entry_price),
                current_price: Number(manualPositionForm.current_price || manualPositionForm.avg_entry_price),
                stop_loss: parseOptional(manualPositionForm.stop_loss),
                take_profit: parseOptional(manualPositionForm.take_profit),
                trailing_stop: parseOptional(manualPositionForm.trailing_stop),
                notes: manualPositionForm.notes || null,
                simulation_account_id: mode === "simulation" ? selectedSimulationAccountId : null,
                tags: ["manual", mode],
              };
              await api.createPosition(payload);
              setBanner({ tone: "success", message: `Existing ${mode} position recorded.` });
              setManualPositionOpen(false);
              workspaceState.reload();
            } catch (error) {
              setBanner({ tone: "error", message: error instanceof Error ? error.message : "Manual position failed." });
            }
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field label={<HelpTooltip label="Ticker" help="Choose a validated symbol when possible. If the instrument is not stored locally yet, the backend can still create a local manual asset for bookkeeping." />}>
              <input
                value={manualPositionForm.asset_symbol}
                onChange={(event) => setManualPositionForm((current) => ({ ...current, asset_symbol: event.target.value.toUpperCase() }))}
                className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100"
              />
            </Field>
            <Field label="Name">
              <input value={manualPositionForm.asset_name} onChange={(event) => setManualPositionForm((current) => ({ ...current, asset_name: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Sizing mode">
              <select value={manualPositionForm.sizing_mode} onChange={(event) => setManualPositionForm((current) => ({ ...current, sizing_mode: event.target.value as SizingMode }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
                <option value="amount">By amount</option>
                <option value="quantity">By quantity</option>
              </select>
            </Field>
            <Field label={manualPositionForm.sizing_mode === "amount" ? "Amount" : "Quantity"}>
              <input
                type="number"
                step="0.0001"
                value={manualPositionForm.sizing_mode === "amount" ? manualPositionForm.amount : manualPositionForm.quantity}
                onChange={(event) =>
                  setManualPositionForm((current) =>
                    current.sizing_mode === "amount" ? { ...current, amount: event.target.value } : { ...current, quantity: event.target.value }
                  )
                }
                className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100"
              />
            </Field>
            <Field label="Entry price">
              <input type="number" step="0.0001" value={manualPositionForm.avg_entry_price} onChange={(event) => setManualPositionForm((current) => ({ ...current, avg_entry_price: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Current price">
              <input type="number" step="0.0001" value={manualPositionForm.current_price} onChange={(event) => setManualPositionForm((current) => ({ ...current, current_price: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label={<HelpTooltip label="Stop loss" help="Automatically closes the trade if price moves against you to this level." />}>
              <input type="number" step="0.0001" value={manualPositionForm.stop_loss} onChange={(event) => setManualPositionForm((current) => ({ ...current, stop_loss: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label={<HelpTooltip label="Take profit" help="Automatically closes the trade once the target profit price is reached." />}>
              <input type="number" step="0.0001" value={manualPositionForm.take_profit} onChange={(event) => setManualPositionForm((current) => ({ ...current, take_profit: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
          </div>
          <Field label={<HelpTooltip label="Trailing stop" help="Moves the stop upward as price rises, helping protect profits." />}>
            <input type="number" step="0.0001" value={manualPositionForm.trailing_stop} onChange={(event) => setManualPositionForm((current) => ({ ...current, trailing_stop: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </Field>
          <Field label="Notes">
            <textarea rows={3} value={manualPositionForm.notes} onChange={(event) => setManualPositionForm((current) => ({ ...current, notes: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </Field>
          <button className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-500/20">Record existing position</button>
        </form>
      </Dialog>

      <Dialog
        open={Boolean(stopDialogPosition)}
        title="Manage stops"
        description="Adjust protective levels in one place. The decision trail records whether stops began as signal suggestions, ticket defaults, current position settings, or manual edits."
        actions={
          <button type="button" onClick={() => setStopDialogPosition(null)} className="rounded-xl border border-border px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
            Close
          </button>
        }
      >
        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!stopDialogPosition) return;
            try {
              const updater = mode === "live" ? api.updateLiveStops : api.updateSimulationStops;
              await updater(stopDialogPosition.id, {
                stop_loss: parseOptional(stopForm.stop_loss),
                take_profit: parseOptional(stopForm.take_profit),
                trailing_stop: parseOptional(stopForm.trailing_stop),
                notes: stopForm.notes || null,
                manual_override: true,
              });
              setBanner({ tone: "success", message: `Stops updated for ${stopDialogPosition.symbol}.` });
              setStopDialogPosition(null);
              workspaceState.reload();
            } catch (error) {
              setBanner({ tone: "error", message: error instanceof Error ? error.message : "Stop update failed." });
            }
          }}
        >
          <div className="grid gap-4 md:grid-cols-3">
            <Field label={<HelpTooltip label="Stop loss" help="Automatically closes the trade if price moves against you to this level." />}>
              <input type="number" step="0.0001" value={stopForm.stop_loss} onChange={(event) => setStopForm((current) => ({ ...current, stop_loss: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label={<HelpTooltip label="Take profit" help="Automatically closes the trade once the target profit price is reached." />}>
              <input type="number" step="0.0001" value={stopForm.take_profit} onChange={(event) => setStopForm((current) => ({ ...current, take_profit: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label={<HelpTooltip label="Trailing stop" help="Moves the stop upward as price rises, helping protect profits." />}>
              <input type="number" step="0.0001" value={stopForm.trailing_stop} onChange={(event) => setStopForm((current) => ({ ...current, trailing_stop: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
          </div>
          <Field label="Notes">
            <textarea rows={3} value={stopForm.notes} onChange={(event) => setStopForm((current) => ({ ...current, notes: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </Field>
          <button className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 hover:bg-emerald-500/20">Save stop settings</button>
        </form>
      </Dialog>

      <Dialog
        open={Boolean(closeDialogPosition)}
        title="Close position"
        description="Enter a percentage to close part of the line. Leave it blank to close 100%."
        actions={
          <button type="button" onClick={() => setCloseDialogPosition(null)} className="rounded-xl border border-border px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
            Close
          </button>
        }
      >
        <div className="space-y-4">
          <div className="rounded-2xl border border-border bg-black/20 p-4 text-sm text-slate-300">
            {closeDialogPosition ? (
              <>
                <div className="font-semibold text-slate-100">{closeDialogPosition.symbol}</div>
                <div className="mt-2">Current quantity: {formatQuantity(Math.abs(closeDialogPosition.quantity), 6)}</div>
                <div className="mt-1">Preview close size: {formatQuantity(closePreviewQty || Math.abs(closeDialogPosition.quantity), 6)}</div>
              </>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {["10", "25", "50", "100"].map((value) => (
              <button key={value} type="button" onClick={() => setClosePercent(value)} className="rounded-full border border-border px-3 py-2 text-xs text-slate-300 hover:bg-white/5">
                {value}%
              </button>
            ))}
          </div>
          <Field label="Close percent">
            <input type="number" min="0" max="100" step="0.01" value={closePercent} onChange={(event) => setClosePercent(event.target.value)} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </Field>
          <button
            type="button"
            onClick={async () => {
              if (!closeDialogPosition) return;
              try {
                const closer = mode === "live" ? api.closeLivePosition : api.closeSimulationPosition;
                await closer(closeDialogPosition.id, { closePercent: closePercent ? Number(closePercent) : undefined });
                setBanner({ tone: "success", message: `${closeDialogPosition.symbol} close request applied.` });
                setCloseDialogPosition(null);
                workspaceState.reload();
              } catch (error) {
                setBanner({ tone: "error", message: error instanceof Error ? error.message : "Position close failed." });
              }
            }}
            className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-sm text-rose-100 hover:bg-rose-500/20"
          >
            Confirm close
          </button>
        </div>
      </Dialog>

      <Dialog
        open={Boolean(detailPosition)}
        title="Position details"
        description="This detail view keeps the dense table clean while still exposing notes, provenance, and management metadata."
        actions={
          <button type="button" onClick={() => setDetailPosition(null)} className="rounded-xl border border-border px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
            Close
          </button>
        }
      >
        {detailPosition ? (
          <div className="grid gap-4 md:grid-cols-2">
            <ReviewStat label="Symbol" value={`${detailPosition.symbol} · ${detailPosition.asset_name}`} />
            <ReviewStat label="Mode" value={detailPosition.mode} />
            <ReviewStat label="Quantity" value={formatQuantity(detailPosition.quantity, 6)} />
            <ReviewStat label="Average entry" value={formatCurrency(detailPosition.avg_entry_price, detailPosition.asset_currency)} />
            <ReviewStat label="Current price" value={formatCurrency(detailPosition.current_price, detailPosition.asset_currency)} />
            <ReviewStat label="Provider / model" value={`${detailPosition.provider_type || "manual"} / ${detailPosition.model_name || "-"}`} />
            <ReviewStat label="Strategy" value={detailPosition.strategy_name || "-"} />
            <ReviewStat label="Notes" value={detailPosition.notes || "-"} />
          </div>
        ) : null}
      </Dialog>

      <SignalTraceDialog
        open={Boolean(selectedSignal)}
        signal={selectedSignal}
        trace={signalTrace}
        loading={signalTraceLoading}
        error={signalTraceError}
        onClose={() => {
          setSelectedSignal(null);
          setSignalTrace(null);
          setSignalTraceError(null);
        }}
        actions={
          (() => {
            const laneStatus = signalTrace?.signal?.lane_statuses?.[mode] || selectedSignal?.lane_statuses?.[mode] || "candidate";
            const buttonLabel =
              mode === "live"
                ? laneStatus === "candidate"
                  ? "Send to live review"
                  : `Live: ${laneStatus}`
                : laneStatus === "candidate"
                  ? "Approve for simulation"
                  : `Simulation: ${laneStatus}`;

            return (
              <button
                type="button"
                disabled={laneStatus !== "candidate" || signalApproveBusy}
                onClick={handleApproveCurrentSignal}
                className={`rounded-xl border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60 ${
                  mode === "live"
                    ? "border-rose-500/30 bg-rose-500/10 text-rose-100 hover:bg-rose-500/20"
                    : "border-cyan-500/30 bg-cyan-500/10 text-cyan-100 hover:bg-cyan-500/20"
                }`}
                title={
                  laneStatus === "candidate"
                    ? mode === "live"
                      ? "Queue this shared signal for guarded live review."
                      : "Queue this shared signal for the simulation workflow."
                    : "This signal already has a recorded outcome in the current lane."
                }
              >
                {signalApproveBusy ? "Saving..." : buttonLabel}
              </button>
            );
          })()
        }
      />
      <ProvenanceDialog
        open={Boolean(provenance.target)}
        signal={provenance.signal}
        trace={provenance.trace}
        loading={provenance.loading}
        error={provenance.error}
        onClose={provenance.closeTrace}
      />
    </div>
  );
}

function AccountSummaryPanel({
  mode,
  workspaceData,
  simulationAccounts,
  brokerAccounts,
  brokerSyncingId,
  selectedSimulationAccountId,
  onChangeSimulationAccount,
  onResetSimulation,
  onSaveSimulationSettings,
  onSyncLiveBroker,
}: {
  mode: TradingMode;
  workspaceData: TradingWorkspaceData;
  simulationAccounts: Array<Record<string, unknown>>;
  brokerAccounts: Array<Record<string, unknown>>;
  brokerSyncingId: string | null;
  selectedSimulationAccountId: string;
  onChangeSimulationAccount: (value: string) => void;
  onResetSimulation: () => void;
  onSaveSimulationSettings: (payload: Record<string, unknown>) => Promise<void>;
  onSyncLiveBroker: (brokerAccountId?: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState({
    starting_cash: 1000,
    fees_bps: 5,
    slippage_bps: 2,
    latency_ms: 50,
    min_cash_reserve_percent: "",
    short_enabled: false,
    short_borrow_fee_bps: 0,
    short_margin_requirement: 1.5,
    partial_fill_ratio: 1,
    enforce_market_hours: false,
  });

  useEffect(() => {
    if (mode !== "simulation") return;
    const current = simulationAccounts.find((account) => account.id === selectedSimulationAccountId);
    if (!current) return;
    setDraft({
      starting_cash: Number(current.starting_cash || 1000),
      fees_bps: Number(current.fees_bps || 0),
      slippage_bps: Number(current.slippage_bps || 0),
      latency_ms: Number(current.latency_ms || 0),
      min_cash_reserve_percent:
        current.min_cash_reserve_percent === null || current.min_cash_reserve_percent === undefined
          ? ""
          : String(Number(current.min_cash_reserve_percent) * 100),
      short_enabled: Boolean(current.short_enabled),
      short_borrow_fee_bps: Number(current.short_borrow_fee_bps || 0),
      short_margin_requirement: Number(current.short_margin_requirement || 1.5),
      partial_fill_ratio: Number(current.partial_fill_ratio || 1),
      enforce_market_hours: Boolean(current.enforce_market_hours),
    });
  }, [mode, selectedSimulationAccountId, simulationAccounts]);

  return (
    <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Account summary</div>
          <div className="mt-1 text-sm text-slate-400">{workspaceData.account.safety_message}</div>
        </div>
        <StatusBadge status={workspaceData.account.status} />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <SummaryChip label="Open positions" value={String(workspaceData.account.open_positions_count)} />
        <SummaryChip label="Active orders" value={String(workspaceData.account.active_orders_count)} />
        <SummaryChip label="Trade count" value={String(workspaceData.account.total_trades_count)} />
        <SummaryChip label="Execution" value={workspaceData.account.live_execution_enabled ? "enabled" : "guarded"} />
        <SummaryChip label="Cash reserve" value={`${formatPct(workspaceData.account.cash_reserve_percent || 0)} · ${formatCurrency(workspaceData.account.cash_reserve_amount || 0, workspaceData.account.base_currency)}`} />
        <SummaryChip label="Available to trade" value={formatCurrency(workspaceData.account.available_to_trade_cash || 0, workspaceData.account.base_currency)} />
      </div>

      {mode === "simulation" ? (
        <div className="mt-4 space-y-4 rounded-2xl border border-border bg-black/20 p-4">
          <div className="text-sm font-semibold text-slate-100">Simulation settings with live-workflow parity</div>
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Active simulation account">
              <select value={selectedSimulationAccountId} onChange={(event) => onChangeSimulationAccount(event.target.value)} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
                {simulationAccounts.map((account) => (
                  <option key={String(account.id)} value={String(account.id)}>
                    {String(account.name)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Starting balance">
              <input type="number" value={draft.starting_cash} onChange={(event) => setDraft((current) => ({ ...current, starting_cash: Number(event.target.value) }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Fees (bps)">
              <input type="number" value={draft.fees_bps} onChange={(event) => setDraft((current) => ({ ...current, fees_bps: Number(event.target.value) }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Slippage (bps)">
              <input type="number" value={draft.slippage_bps} onChange={(event) => setDraft((current) => ({ ...current, slippage_bps: Number(event.target.value) }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Latency (ms)">
              <input type="number" value={draft.latency_ms} onChange={(event) => setDraft((current) => ({ ...current, latency_ms: Number(event.target.value) }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label={<HelpTooltip label="Cash reserve override" help="Leave blank to inherit the shared cash reserve rule. Enter a percentage to give this model account its own reserve." />}>
              <input type="number" step="0.5" value={draft.min_cash_reserve_percent} onChange={(event) => setDraft((current) => ({ ...current, min_cash_reserve_percent: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" placeholder="Inherit" />
            </Field>
            <ToggleField
              label={<HelpTooltip label="Short simulation" help="Allows this simulation account to open short trades that profit if price falls. Live availability depends on broker support and is disabled for Trading212 here." />}
              checked={draft.short_enabled}
              onChange={(checked) => setDraft((current) => ({ ...current, short_enabled: checked }))}
            />
            <Field label={<HelpTooltip label="Short borrow fee" help="One-period borrow fee scaffold applied when covering simulated short exposure." />}>
              <input type="number" value={draft.short_borrow_fee_bps} onChange={(event) => setDraft((current) => ({ ...current, short_borrow_fee_bps: Number(event.target.value) }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label={<HelpTooltip label="Short margin requirement" help="Multiplier of short notional required as available cash before opening a simulated short." />}>
              <input type="number" step="0.1" min="1" value={draft.short_margin_requirement} onChange={(event) => setDraft((current) => ({ ...current, short_margin_requirement: Number(event.target.value) }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label={<HelpTooltip label="Partial fill ratio" help="Scaffold for partial fills. 1 means full fills; 0.5 fills half the requested quantity." />}>
              <input type="number" step="0.05" min="0" max="1" value={draft.partial_fill_ratio} onChange={(event) => setDraft((current) => ({ ...current, partial_fill_ratio: Number(event.target.value) }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <ToggleField
              label={<HelpTooltip label="Market-hours guard" help="Simulation setting scaffold for restricting orders to market-hours windows." />}
              checked={draft.enforce_market_hours}
              onChange={(checked) => setDraft((current) => ({ ...current, enforce_market_hours: checked }))}
            />
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() =>
                onSaveSimulationSettings({
                  ...draft,
                  min_cash_reserve_percent:
                    draft.min_cash_reserve_percent === "" ? null : Math.max(0, Number(draft.min_cash_reserve_percent)) / 100,
                })
              }
              className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-500/20"
            >
              Save sim settings
            </button>
            <button type="button" onClick={onResetSimulation} className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 hover:bg-amber-500/20">
              Reset simulation account
            </button>
          </div>
          <SimulationModelComparison
            accounts={simulationAccounts}
            selectedSimulationAccountId={selectedSimulationAccountId}
            onChangeSimulationAccount={onChangeSimulationAccount}
          />
        </div>
      ) : (
        <div className="mt-4 space-y-3 rounded-2xl border border-border bg-black/20 p-4">
          <div className="text-sm font-semibold text-slate-100">Broker status and live safety</div>
          {brokerAccounts.map((account) => (
            <div key={String(account.id)} className="rounded-xl border border-border px-3 py-3">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div>
                  <div className="text-sm text-slate-100">{String(account.name)}</div>
                  <div className="text-xs text-slate-400">
                    {String(account.broker_type)} · {String(account.mode)}
                  </div>
                  <div className="mt-2 text-xs text-slate-500">
                    {String(account.capability_message || "Broker scaffold status available in this workspace.")}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={String(account.status || "scaffolded")} />
                  {Boolean(account.live_trading_enabled) ? <StatusBadge status="enabled" /> : <StatusBadge status="guarded" />}
                  {Boolean(account.supports_sync) ? <StatusBadge status="ok" /> : <StatusBadge status="disabled" />}
                  <button
                    type="button"
                    onClick={() => onSyncLiveBroker(String(account.id))}
                    disabled={!account.supports_sync || brokerSyncingId === String(account.id)}
                    className="rounded-xl border border-border px-3 py-2 text-xs text-slate-200 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                    title="Runs the broker account sync scaffold and updates the latest sync status shown here."
                  >
                    {brokerSyncingId === String(account.id) ? "Syncing..." : "Sync now"}
                  </button>
                </div>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                <SummaryChip label="Execution" value={account.supports_execution ? "supported" : "guarded/off"} />
                <SummaryChip label="Sync" value={account.supports_sync ? "available" : "not supported"} />
                <SummaryChip label="Cash" value={account.available_cash === null || account.available_cash === undefined ? "Not synced" : formatCurrency(Number(account.available_cash), String(account.currency || "USD"))} />
                <SummaryChip label="Portfolio" value={account.total_value === null || account.total_value === undefined ? "Not synced" : formatCurrency(Number(account.total_value), String(account.currency || "USD"))} />
                <SummaryChip label="Synced positions" value={String((account.synced_positions as Array<Record<string, unknown>> | undefined)?.length || 0)} />
                <SummaryChip label="Synced pies" value={String((account.synced_pies as Array<Record<string, unknown>> | undefined)?.length || 0)} />
                <SummaryChip label="Last sync status" value={String(account.last_sync_status || "Never run")} />
                <SummaryChip label="Last sync time" value={String(account.last_sync_completed_at || account.last_sync_started_at || "n/a")} />
              </div>
              {Array.isArray(account.synced_pies) && account.synced_pies.length ? (
                <div className="mt-3 rounded-2xl border border-border bg-black/20 p-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Trading212 pies</div>
                  <div className="mt-2 grid gap-2 md:grid-cols-2">
                    {account.synced_pies.slice(0, 6).map((pie) => (
                      <div key={String(pie.id)} className="rounded-xl border border-border/70 px-3 py-2 text-xs text-slate-300">
                        <div className="font-semibold text-slate-100">Pie #{String(pie.id)}</div>
                        <div className="mt-1">Status: {String(pie.status || "unknown")}</div>
                        <div>Cash: {formatCurrency(Number(pie.cash || 0), String(account.currency || "USD"))}</div>
                        <div>Result: {formatCurrency(Number(pie.result || 0), String(account.currency || "USD"))}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {account.last_sync_message ? <div className="mt-3 text-xs text-slate-400">{String(account.last_sync_message)}</div> : null}
            </div>
          ))}
          {!brokerAccounts.length ? <div className="text-sm text-slate-500">No broker account is configured yet.</div> : null}
        </div>
      )}
    </section>
  );
}

function SimulationModelComparison({
  accounts,
  selectedSimulationAccountId,
  onChangeSimulationAccount,
}: {
  accounts: Array<Record<string, unknown>>;
  selectedSimulationAccountId: string;
  onChangeSimulationAccount: (value: string) => void;
}) {
  if (!accounts.length) return null;
  return (
    <div className="rounded-2xl border border-border bg-black/20 p-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-100">Model account comparison</div>
          <div className="mt-1 text-xs text-slate-400">Each provider/model gets its own simulated cash, positions, orders, trades, and PnL so models can compete cleanly.</div>
        </div>
        <StatusBadge status="simulation" />
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr>
              <th>Model account</th>
              <th>Cash</th>
              <th>Reserved</th>
              <th>Available</th>
              <th>Value</th>
              <th>Return</th>
              <th>Win rate</th>
              <th>Profit factor</th>
              <th>Drawdown</th>
              <th>Trades</th>
              <th>Rejected</th>
              <th>Invalid</th>
              <th>Shorts</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((account) => (
              <tr key={String(account.id)} className={String(account.id) === selectedSimulationAccountId ? "bg-cyan-500/5" : undefined}>
                <td>
                  <button type="button" onClick={() => onChangeSimulationAccount(String(account.id))} className="text-left hover:text-cyan-100">
                    <div className="font-semibold text-slate-100">{String(account.name)}</div>
                    <div className="text-[11px] text-slate-400">{String(account.provider_type || "manual")} · {String(account.model_name || "model unset")}</div>
                  </button>
                </td>
                <td>{formatCurrency(Number(account.cash_balance || 0))}</td>
                <td>{formatCurrency(Number(account.reserved_cash || account.cash_reserve_amount || 0))}</td>
                <td>{formatCurrency(Number(account.available_to_trade_cash || 0))}</td>
                <td>{formatCurrency(Number(account.portfolio_value ?? account.cash_balance ?? 0))}</td>
                <td>{formatPct(Number(account.total_return || 0))}</td>
                <td>{formatPct(Number(account.win_rate || 0))}</td>
                <td>{Number(account.profit_factor || 0).toFixed(2)}</td>
                <td>{formatPct(Number(account.max_drawdown || 0))}</td>
                <td>{String(account.trade_count ?? 0)}</td>
                <td>{String(account.rejected_trade_count ?? 0)}</td>
                <td>{formatPct(Number(account.invalid_signal_rate || 0))}</td>
                <td>{Boolean(account.short_enabled) ? "Enabled" : "Off"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReplayBacktestPanel({
  open,
  onToggle,
  workspaceData,
  simulationAccounts,
  replayRuns,
  loading,
  form,
  onChange,
  onCreate,
}: {
  open: boolean;
  onToggle: () => void;
  workspaceData: TradingWorkspaceData;
  simulationAccounts: Array<Record<string, unknown>>;
  replayRuns: ReplayRun[];
  loading: boolean;
  form: {
    date_start: string;
    date_end: string;
    starting_cash: string;
    selected_models: string[];
    symbols: string[];
    fees_bps: string;
    slippage_bps: string;
    cash_reserve_percent: string;
    short_enabled: boolean;
    enforce_market_hours: boolean;
  };
  onChange: Dispatch<SetStateAction<any>>;
  onCreate: () => Promise<void>;
}) {
  const modelOptions = Array.from(new Set(simulationAccounts.map((account) => String(account.provider_type || "")).filter(Boolean)));
  const symbolOptions = workspaceData.assets.map((asset) => asset.symbol).slice(0, 12);
  const latestRun = replayRuns[0];
  return (
    <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <button type="button" onClick={onToggle} className="flex w-full flex-col gap-3 text-left md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Replay / Backtest scaffold</div>
          <div className="mt-1 text-sm text-slate-400">
            Runs selected models over the same historical window using stored signals and market snapshots. Results are isolated from normal simulation balances.
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status="scaffold" />
          <span className="rounded-full border border-border px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-200">
            {open ? "Close" : "Open"}
          </span>
        </div>
      </button>
      {open ? (
        <div className="mt-4 space-y-4">
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            Scaffold / limited historical data: fills use stored prices at or before each replay timestamp and do not write normal simulation orders, trades, positions, or cash.
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Field label="Start">
              <input type="datetime-local" value={form.date_start} onChange={(event) => onChange((current: any) => ({ ...current, date_start: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="End">
              <input type="datetime-local" value={form.date_end} onChange={(event) => onChange((current: any) => ({ ...current, date_end: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Starting cash">
              <input type="number" value={form.starting_cash} onChange={(event) => onChange((current: any) => ({ ...current, starting_cash: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Cash reserve %">
              <input type="number" value={form.cash_reserve_percent} onChange={(event) => onChange((current: any) => ({ ...current, cash_reserve_percent: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Fees (bps)">
              <input type="number" value={form.fees_bps} onChange={(event) => onChange((current: any) => ({ ...current, fees_bps: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Slippage (bps)">
              <input type="number" value={form.slippage_bps} onChange={(event) => onChange((current: any) => ({ ...current, slippage_bps: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <ToggleField label="Short simulation" checked={form.short_enabled} onChange={(checked) => onChange((current: any) => ({ ...current, short_enabled: checked }))} />
            <ToggleField label="Market-hours guard" checked={form.enforce_market_hours} onChange={(checked) => onChange((current: any) => ({ ...current, enforce_market_hours: checked }))} />
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <CheckList
              title="Replay models"
              description="All selected models consume the same chronological market/news window."
              items={modelOptions.map((provider) => ({ value: provider, label: provider }))}
              value={form.selected_models}
              onChange={(next) => onChange((current: any) => ({ ...current, selected_models: next }))}
            />
            <CheckList
              title="Replay symbols"
              description="Historical snapshots and stored signals are filtered to this symbol set."
              items={symbolOptions.map((symbol) => ({ value: symbol, label: symbol }))}
              value={form.symbols}
              onChange={(next) => onChange((current: any) => ({ ...current, symbols: next }))}
            />
          </div>
          <button type="button" onClick={onCreate} className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-500/20">
            Create replay run
          </button>

          <div className="rounded-2xl border border-border bg-black/20 p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-slate-100">Replay results</div>
              <SummaryChip label="Runs" value={loading ? "Loading" : String(replayRuns.length)} />
            </div>
            {!latestRun ? (
              <div className="mt-4 text-sm text-slate-500">No replay runs yet.</div>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <div className="mb-3 text-xs text-slate-400">
                  Latest: {latestRun.name} · {formatDateTime(latestRun.created_at)} · {latestRun.status}
                </div>
                <table className="min-w-full text-xs">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Return</th>
                      <th>Drawdown</th>
                      <th>Sharpe</th>
                      <th>Sortino</th>
                      <th>Win rate</th>
                      <th>Profit factor</th>
                      <th>Trades</th>
                      <th>Rejected</th>
                      <th>Invalid</th>
                    </tr>
                  </thead>
                  <tbody>
                    {latestRun.results.map((result) => (
                      <tr key={result.id}>
                        <td>
                          <div className="font-semibold text-slate-100">{result.provider_type}</div>
                          <div className="text-[11px] text-slate-400">{result.model_name || "model unset"}</div>
                        </td>
                        <td>{formatPct(result.total_return)}</td>
                        <td>{formatPct(result.max_drawdown)}</td>
                        <td>{result.sharpe.toFixed(2)}</td>
                        <td>{result.sortino.toFixed(2)}</td>
                        <td>{formatPct(result.win_rate)}</td>
                        <td>{result.profit_factor.toFixed(2)}</td>
                        <td>{result.trades}</td>
                        <td>{result.rejected_trades}</td>
                        <td>{result.invalid_signals}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function OrderEntryPanel({
  mode,
  workspaceData,
  providerOptions,
  searchQuery,
  searchLoading,
  searchMessage,
  searchResults,
  orderForm,
  selectedAsset,
  currentCurrency,
  derivedQuantity,
  orderNotional,
  embedded = false,
  onSearchQueryChange,
  onChooseAsset,
  onChange,
  onOpenExistingPosition,
  onOpenReview,
}: {
  mode: TradingMode;
  workspaceData: TradingWorkspaceData;
  providerOptions: string[];
  searchQuery: string;
  searchLoading: boolean;
  searchMessage: string;
  searchResults: AssetSearchResult[];
  orderForm: Record<string, string>;
  selectedAsset: Asset | null;
  currentCurrency: string;
  derivedQuantity: number;
  orderNotional: number;
  embedded?: boolean;
  onSearchQueryChange: (value: string) => void;
  onChooseAsset: (asset: AssetSearchResult) => void;
  onChange: Dispatch<SetStateAction<any>>;
  onOpenExistingPosition: () => void;
  onOpenReview: () => void;
}) {
  return (
    <section className={embedded ? "rounded-2xl border border-border bg-black/20 p-4" : "rounded-2xl border border-border bg-panel/90 p-4 shadow-panel"}>
      {!embedded ? <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Manual trading controls</div>
          <div className="mt-1 text-sm text-slate-400">
            The simulation and live tickets share the same structure so you can practise the workflow before you switch to the guarded live lane.
          </div>
          <div className="mt-2 text-xs text-slate-500">
            Need to track something you already bought or sold elsewhere? Use <span className="font-semibold text-slate-300">Add existing position</span>. It records the holding here without sending a new order.
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={mode === "live" ? "live" : "simulation"} />
          <button
            type="button"
            onClick={onOpenExistingPosition}
            className="rounded-xl border border-border px-3 py-2 text-xs font-medium text-slate-200 hover:bg-white/5"
            title="Records a position that already exists in your broker or outside this order ticket so this workspace can manage stops and reporting."
          >
            Add existing position
          </button>
        </div>
      </div> : null}

      <div className={embedded ? "grid gap-4" : "mt-4 grid gap-4"}>
        <Field label={<HelpTooltip label="Symbol selector" help="Search by ticker or company name. Local assets appear immediately, and broker-backed validation can add verified matches when available." />}>
          <div className="space-y-2">
            <input value={searchQuery} onChange={(event) => onSearchQueryChange(event.target.value)} placeholder="Search ticker or instrument name" className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            <div className="rounded-2xl border border-border bg-black/20 p-3">
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Matches</div>
              {searchLoading ? <div className="mt-2 text-sm text-slate-400">Searching...</div> : null}
              {!searchLoading && searchResults.length ? (
                <div className="mt-3 space-y-2">
                  {searchResults.map((result) => (
                    <button key={result.key} type="button" onClick={() => onChooseAsset(result)} className="flex w-full items-center justify-between rounded-xl border border-border px-3 py-3 text-left hover:bg-white/5">
                      <div>
                        <div className="font-semibold text-slate-100">{result.display_symbol}</div>
                        <div className="text-xs text-slate-400">{result.name}</div>
                      </div>
                      <div className="text-right text-xs text-slate-400">
                        <div>{result.source_label}</div>
                        <div>{result.currency}</div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : !searchLoading ? (
                <div className="mt-2 text-sm text-slate-400">{searchMessage}</div>
              ) : null}
            </div>
          </div>
        </Field>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Field label="Side">
            <select value={orderForm.side} onChange={(event) => onChange((current: any) => ({ ...current, side: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
              {TRADE_ACTIONS.filter((action) => {
                if (mode === "live" && ["short", "cover_short"].includes(action.value)) return Boolean(workspaceData.account.metadata.short_supported);
                return true;
              }).map((action) => (
                <option key={action.value} value={action.value}>
                  {action.label}
                </option>
              ))}
            </select>
            <div className="mt-1 text-xs text-slate-500">
              {TRADE_ACTIONS.find((action) => action.value === orderForm.side)?.help || "Order action."}
            </div>
          </Field>
          <Field label="Order type">
            <select value={orderForm.order_type} onChange={(event) => onChange((current: any) => ({ ...current, order_type: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
              <option value="market">Market</option>
              <option value="limit">Limit</option>
            </select>
          </Field>
          <Field label="Sizing">
            <select value={orderForm.sizing_mode} onChange={(event) => onChange((current: any) => ({ ...current, sizing_mode: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
              <option value="amount">Amount</option>
              <option value="quantity">Quantity</option>
            </select>
          </Field>
          <Field label={orderForm.sizing_mode === "amount" ? "Amount" : "Quantity"}>
            <input
              type="number"
              step="0.0001"
              value={orderForm.sizing_mode === "amount" ? orderForm.amount : orderForm.quantity}
              onChange={(event) =>
                onChange((current: any) =>
                  current.sizing_mode === "amount" ? { ...current, amount: event.target.value } : { ...current, quantity: event.target.value }
                )
              }
              className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100"
            />
          </Field>
          <Field label={orderForm.order_type === "limit" ? "Limit price" : "Reference price"}>
            <input type="number" step="0.0001" value={orderForm.requested_price} onChange={(event) => onChange((current: any) => ({ ...current, requested_price: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </Field>
          <Field label="Strategy tag">
            <select value={orderForm.strategy_name} onChange={(event) => onChange((current: any) => ({ ...current, strategy_name: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
              {workspaceData.strategies.map((strategy) => (
                <option key={strategy.id} value={strategy.slug}>
                  {strategy.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Provider / model">
            <select value={orderForm.provider_type} onChange={(event) => onChange((current: any) => ({ ...current, provider_type: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
              {providerOptions.map((provider) => (
                <option key={provider} value={provider}>
                  {provider}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Risk profile">
            <select value={orderForm.risk_profile} onChange={(event) => onChange((current: any) => ({ ...current, risk_profile: event.target.value, stop_loss: "", take_profit: "", trailing_stop: "" }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
              <option value="conservative">Conservative</option>
              <option value="balanced">Balanced</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </Field>
          <Field label={<HelpTooltip label="Stop loss" help="Automatically closes the trade if price moves against you to this level." />}>
            <input type="number" step="0.0001" value={orderForm.stop_loss} onChange={(event) => onChange((current: any) => ({ ...current, stop_loss: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </Field>
          <Field label={<HelpTooltip label="Take profit" help="Automatically closes the trade once the target profit price is reached." />}>
            <input type="number" step="0.0001" value={orderForm.take_profit} onChange={(event) => onChange((current: any) => ({ ...current, take_profit: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </Field>
          <Field label={<HelpTooltip label="Trailing stop" help="Moves the stop upward as price rises, helping protect profits." />}>
            <input type="number" step="0.0001" value={orderForm.trailing_stop} onChange={(event) => onChange((current: any) => ({ ...current, trailing_stop: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </Field>
          <Field label="Link signal">
            <select value={orderForm.signal_id} onChange={(event) => onChange((current: any) => ({ ...current, signal_id: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
              <option value="">No linked signal</option>
              {workspaceData.signals.map((signal) => (
                <option key={signal.id} value={signal.id}>
                  {signal.symbol} · {signal.action.toUpperCase()} · {(signal.confidence * 100).toFixed(0)}%
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="Notes / entry rationale">
          <textarea value={orderForm.notes} onChange={(event) => onChange((current: any) => ({ ...current, notes: event.target.value }))} rows={3} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
        </Field>

        <div className="rounded-2xl border border-border bg-black/20 p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Review preview</div>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <SummaryChip label="Selected asset" value={selectedAsset ? `${selectedAsset.symbol} · ${selectedAsset.name}` : orderForm.asset_symbol || "-"} />
            <SummaryChip label="Estimated quantity" value={formatQuantity(derivedQuantity, 6)} />
            <SummaryChip label="Estimated notional" value={formatCurrency(orderNotional, currentCurrency)} />
            <SummaryChip label="Reserved cash" value={formatCurrency(workspaceData.account.cash_reserve_amount || 0, currentCurrency)} />
            <SummaryChip label="Available after reserve" value={formatCurrency(workspaceData.account.available_to_trade_cash || 0, currentCurrency)} />
          </div>
        </div>

        <button type="button" onClick={onOpenReview} className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-500/20">
          Review order
        </button>
      </div>
    </section>
  );
}

function AutomationControlPanel({
  mode,
  workspaceData,
  providerOptions,
  automationForm,
  embedded = false,
  onChange,
  onSave,
  onRun,
}: {
  mode: TradingMode;
  workspaceData: TradingWorkspaceData;
  providerOptions: string[];
  automationForm: TradingAutomationProfile;
  embedded?: boolean;
  onChange: Dispatch<SetStateAction<TradingAutomationProfile | null>>;
  onSave: () => Promise<void>;
  onRun: () => Promise<void>;
}) {
  const inheritsLive = mode === "simulation" && automationForm.inherit_from_live;

  return (
    <section className={embedded ? "rounded-2xl border border-border bg-black/20 p-4" : "rounded-2xl border border-border bg-panel/90 p-4 shadow-panel"}>
      {!embedded ? <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Automation controls</div>
          <div className="mt-1 text-sm text-slate-400">
            Automation can be fully automatic or semi-automatic, but every eligible order still goes through the same risk engine as the manual ticket.
          </div>
        </div>
        <StatusBadge status={automationForm.automation_enabled ? "enabled" : "disabled"} />
      </div> : null}
      {mode === "simulation" ? (
        <div className="mt-4 space-y-3">
          <ToggleField
            label={<HelpTooltip label="Use same settings as Live" help="Keeps Simulation aligned with the live automation policy so your training runs mirror the same strategy, confidence, sizing, and stop defaults." />}
            checked={automationForm.inherit_from_live}
            onChange={(checked) => onChange((current) => (current ? { ...current, inherit_from_live: checked } : current))}
          />
          {inheritsLive ? (
            <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100">
              Simulation is currently inheriting the live automation policy. You can still keep the simulation lane enabled or disabled separately, but the strategy filters, confidence threshold, order notional, and stop defaults now come from live.
            </div>
          ) : (
            <div className="rounded-2xl border border-border bg-black/20 px-4 py-3 text-sm text-slate-300">
              Simulation is using its own automation overrides. This is useful when you want to train with a looser policy before promoting changes into live.
            </div>
          )}
        </div>
      ) : null}
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <ToggleField
          label={<HelpTooltip label="Automation enabled" help="Allows the system to place or prepare eligible trades without re-entering the ticket manually." />}
          checked={automationForm.automation_enabled}
          onChange={(checked) => onChange((current) => (current ? { ...current, automation_enabled: checked } : current))}
          disabled={inheritsLive}
        />
        <ToggleField
          label={
            <HelpTooltip
              label="Scheduled execution"
              help={
                mode === "simulation"
                  ? "Runs this simulation automation profile on a timer. In fully automatic mode it can create simulated buy/sell orders when eligible signals pass risk checks."
                  : "Runs this live automation profile on a timer only if live trading and broker execution are explicitly enabled. Keep this off unless you understand the live risk."
              }
            />
          }
          checked={automationForm.scheduled_execution_enabled}
          onChange={(checked) => onChange((current) => (current ? { ...current, scheduled_execution_enabled: checked } : current))}
          disabled={inheritsLive}
        />
        <Field label={<HelpTooltip label="Approval mode" help="Semi-automatic prepares a trade and asks for your approval. Fully automatic can submit the order directly if it passes risk checks." />}>
          <select value={automationForm.approval_mode} onChange={(event) => onChange((current) => (current ? { ...current, approval_mode: event.target.value } : current))} disabled={inheritsLive} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100 disabled:opacity-60">
            <option value="manual_only">Manual only</option>
            <option value="semi_automatic">Semi-automatic</option>
            <option value="fully_automatic">Fully automatic</option>
          </select>
        </Field>
        <Field
          label={
            <HelpTooltip
              label="Automation check interval"
              help="How often the scheduled worker is allowed to run this automation profile. The worker scans every minute, then runs only when this interval is due."
            />
          }
          description={automationForm.scheduled_execution_enabled ? `Next due: ${formatDateTime(automationForm.next_scheduled_run_at)}` : "Timer is off until scheduled execution is enabled."}
        >
          <select
            value={automationForm.execution_interval_seconds}
            onChange={(event) => onChange((current) => (current ? { ...current, execution_interval_seconds: Number(event.target.value) } : current))}
            disabled={inheritsLive}
            className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100 disabled:opacity-60"
          >
            <option value={60}>Every 1 minute</option>
            <option value={300}>Every 5 minutes</option>
            <option value={600}>Every 10 minutes</option>
            <option value={900}>Every 15 minutes</option>
            <option value={1800}>Every 30 minutes</option>
          </select>
        </Field>
        <Field label="Confidence threshold">
          <input type="number" step="0.01" min="0" max="1" value={automationForm.confidence_threshold} onChange={(event) => onChange((current) => (current ? { ...current, confidence_threshold: Number(event.target.value) } : current))} disabled={inheritsLive} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100 disabled:opacity-60" />
        </Field>
        <Field label="Default order notional">
          <input type="number" min="1" value={automationForm.default_order_notional} onChange={(event) => onChange((current) => (current ? { ...current, default_order_notional: Number(event.target.value) } : current))} disabled={inheritsLive} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100 disabled:opacity-60" />
        </Field>
        <Field label="Max orders per run">
          <input type="number" min="1" max="10" value={automationForm.max_orders_per_run} onChange={(event) => onChange((current) => (current ? { ...current, max_orders_per_run: Number(event.target.value) } : current))} disabled={inheritsLive} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100 disabled:opacity-60" />
        </Field>
        <Field label="Risk profile">
          <select value={automationForm.risk_profile} onChange={(event) => onChange((current) => (current ? { ...current, risk_profile: event.target.value } : current))} disabled={inheritsLive} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100 disabled:opacity-60">
            <option value="conservative">Conservative</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </Field>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <CheckList
          title="Allowed strategies"
          description="Choose which strategy families are allowed to open or prepare trades."
          items={workspaceData.strategies.map((strategy) => ({ value: strategy.slug, label: strategy.name }))}
          value={automationForm.allowed_strategy_slugs}
          onChange={(next) => onChange((current) => (current ? { ...current, allowed_strategy_slugs: next } : current))}
          disabled={inheritsLive}
        />
        {mode === "live" ? (
          <div className="rounded-2xl border border-border bg-black/20 p-4">
            <div className="font-semibold text-slate-100">Live model lock</div>
            <div className="mt-1 text-sm text-slate-400">Live automation may use exactly one configured live provider/model. Change it in Settings if needed.</div>
            <div className="mt-4 rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-100">
              {String(workspaceData.controls.live_model_provider_type || automationForm.allowed_provider_types[0] || "No live model selected")}
            </div>
          </div>
        ) : (
          <CheckList
            title="Allowed providers"
            description="Keep automation scoped to the provider/model profiles you trust for this lane."
            items={providerOptions.map((provider) => ({ value: provider, label: provider }))}
            value={automationForm.allowed_provider_types}
            onChange={(next) => onChange((current) => (current ? { ...current, allowed_provider_types: next } : current))}
            disabled={inheritsLive}
          />
        )}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {TRADE_ACTIONS.filter((action) => {
          if (mode === "live" && ["short", "cover_short"].includes(action.value)) return Boolean(workspaceData.account.metadata.short_supported);
          return true;
        }).map((action) => (
          <ToggleField
            key={action.value}
            label={<HelpTooltip label={`Allow ${action.label}`} help={action.help} />}
            checked={automationForm.tradable_actions.includes(action.value)}
            onChange={(checked) => onChange((current) => (current ? { ...current, tradable_actions: toggleListValue(current.tradable_actions, action.value, checked) } : current))}
            disabled={inheritsLive}
          />
        ))}
        <ToggleField
          label="Profile enabled"
          checked={automationForm.enabled}
          onChange={(checked) => onChange((current) => (current ? { ...current, enabled: checked } : current))}
        />
      </div>

      <Field label="Automation notes" description="Useful for documenting which strategies or signals should stay gated in this environment.">
        <textarea rows={3} value={automationForm.notes || ""} onChange={(event) => onChange((current) => (current ? { ...current, notes: event.target.value } : current))} disabled={inheritsLive} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100 disabled:opacity-60" />
      </Field>

      <div className="mt-4 rounded-2xl border border-border bg-black/20 p-4 text-sm text-slate-300">
        <div className="font-semibold text-slate-100">Automation timing</div>
        <div className="mt-1">
          {automationForm.scheduled_execution_enabled
            ? `Scheduled worker checks this profile every ${formatInterval(automationForm.execution_interval_seconds)}. ${
                automationForm.approval_mode === "fully_automatic"
                  ? mode === "simulation"
                    ? "Eligible signals can become simulated orders automatically."
                    : "Eligible signals can enter the guarded live workflow automatically."
                  : "Eligible signals are queued for review because approval mode is not fully automatic."
              }`
            : "Scheduled execution is off. Use Run automation now to process eligible signals manually."}
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <SummaryChip label="Last run" value={formatDateTime(automationForm.last_run_at)} />
          <SummaryChip label="Last scheduled run" value={formatDateTime(automationForm.last_scheduled_run_at)} />
          <SummaryChip label="Next scheduled run" value={formatDateTime(automationForm.next_scheduled_run_at)} />
        </div>
        <div className="mt-3 text-slate-400">{automationForm.last_run_message || "Automation has not been run yet."}</div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={onSave} className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-500/20">
          Save automation
        </button>
        <button type="button" onClick={onRun} className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 hover:bg-emerald-500/20">
          Run automation now
        </button>
      </div>
    </section>
  );
}

function RecommendationQueue({
  mode,
  recommendations,
  busySignalId,
  onLoadTicket,
  onReject,
}: {
  mode: TradingMode;
  recommendations: TradingRecommendation[];
  busySignalId: string | null;
  onLoadTicket: (recommendation: TradingRecommendation) => void;
  onReject: (recommendation: TradingRecommendation) => Promise<void>;
}) {
  return (
    <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Approval queue</div>
          <div className="mt-1 text-sm text-slate-400">
            Semi-automatic and manual-only automation runs land here first. Review the ticket before sending it, or reject the recommendation explicitly.
          </div>
        </div>
        <SummaryChip label="Queued" value={String(recommendations.length)} />
      </div>
      {!recommendations.length ? (
        <div className="mt-4 rounded-2xl border border-dashed border-border bg-black/20 px-4 py-4 text-sm text-slate-400">
          No recommendations are waiting in the {mode} queue right now.
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {recommendations.map((recommendation) => (
            <div key={recommendation.signal_id} className="rounded-2xl border border-border bg-black/20 p-4">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-slate-100">{recommendation.symbol}</div>
                    <StatusBadge status={recommendation.status} />
                    <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-[11px] uppercase tracking-[0.14em] text-cyan-200">
                      {recommendation.action}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    {recommendation.asset_name} · {recommendation.strategy_slug || "unlabeled strategy"} · {(recommendation.confidence * 100).toFixed(0)}% confidence
                  </div>
                  <div className="mt-3 text-sm text-slate-300">{recommendation.reason}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => onLoadTicket(recommendation)}
                    className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100 hover:bg-cyan-500/20"
                    title="Loads the approved signal into the shared order review ticket so you can confirm sizing and stops."
                  >
                    Review ticket
                  </button>
                  <button
                    type="button"
                    onClick={() => onReject(recommendation)}
                    disabled={busySignalId === recommendation.signal_id}
                    className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-100 hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                    title="Rejects the queued recommendation and removes it from the operator approval queue."
                  >
                    {busySignalId === recommendation.signal_id ? "Rejecting..." : "Reject"}
                  </button>
                </div>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                <SummaryChip label="Suggested entry" value={recommendation.suggested_entry ? String(recommendation.suggested_entry) : "n/a"} />
                <SummaryChip label="Risk / reward" value={recommendation.estimated_risk_reward ? recommendation.estimated_risk_reward.toFixed(2) : "n/a"} />
                <SummaryChip label="Stop / target" value={`${recommendation.suggested_stop_loss || "-"} / ${recommendation.suggested_take_profit || "-"}`} />
                <SummaryChip label="Queued at" value={recommendation.queued_at.replace("T", " ").slice(0, 16)} />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ExecutionHistoryPanel({
  mode,
  orders,
  trades,
  onViewTrace,
}: {
  mode: TradingMode;
  orders: Order[];
  trades: Trade[];
  onViewTrace: (type: "order" | "trade", item: Order | Trade) => void;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Active {mode} orders</div>
        <TradesTable orders={orders} onViewTrace={onViewTrace} />
      </section>
      <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Recent {mode} executions</div>
        <TradesTable trades={trades} onViewTrace={onViewTrace} />
      </section>
    </div>
  );
}

function Field({
  label,
  description,
  children,
}: {
  label: ReactNode;
  description?: string;
  children: ReactNode;
}) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      <div>{label}</div>
      {description ? <div className="text-xs text-slate-500">{description}</div> : null}
      {children}
    </label>
  );
}

function ToggleField({
  label,
  checked,
  onChange,
  disabled = false,
}: {
  label: ReactNode;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={() => {
        if (!disabled) onChange(!checked);
      }}
      disabled={disabled}
      className="flex items-center justify-between rounded-2xl border border-border bg-black/20 px-4 py-3 text-sm text-slate-300 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
    >
      <span>{label}</span>
      <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${checked ? "bg-emerald-500/15 text-emerald-200" : "bg-slate-500/15 text-slate-400"}`}>
        {checked ? "On" : "Off"}
      </span>
    </button>
  );
}

function CheckList({
  title,
  description,
  items,
  value,
  onChange,
  disabled = false,
}: {
  title: string;
  description: string;
  items: Array<{ value: string; label: string }>;
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-border bg-black/20 p-4">
      <div className="text-sm font-semibold text-slate-100">{title}</div>
      <div className="mt-1 text-xs text-slate-500">{description}</div>
      <div className="mt-3 space-y-2">
        {items.map((item) => {
          const active = value.includes(item.value);
          return (
            <label key={item.value} className="flex items-center justify-between rounded-xl border border-border px-3 py-2 text-sm text-slate-300">
              <span>{item.label}</span>
              <input
                type="checkbox"
                checked={active}
                disabled={disabled}
                onChange={(event) => onChange(toggleListValue(value, item.value, event.target.checked))}
              />
            </label>
          );
        })}
      </div>
    </div>
  );
}

function SummaryChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-black/20 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-1 text-base font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function ReviewStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-black/20 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function InfoRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-black/20 px-3 py-3">
      <div className="mt-0.5 text-slate-400">{icon}</div>
      <div>
        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</div>
        <div className="mt-1 text-sm text-slate-200">{value}</div>
      </div>
    </div>
  );
}

function Banner({ tone, message }: { tone: "success" | "warn" | "error"; message: string }) {
  const className =
    tone === "success"
      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-100"
      : tone === "warn"
        ? "border-amber-500/20 bg-amber-500/10 text-amber-100"
        : "border-rose-500/20 bg-rose-500/10 text-rose-100";
  return <div className={`rounded-2xl border px-4 py-3 text-sm ${className}`}>{message}</div>;
}

function SegmentedControl({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <div className="flex flex-wrap gap-2 rounded-full border border-border bg-black/20 p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.18em] ${value === option.value ? "bg-white/10 text-slate-100" : "text-slate-400 hover:text-slate-200"}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function toLocalSearchResult(asset: Asset): AssetSearchResult {
  return {
    key: `local:${asset.id}`,
    asset_id: asset.id,
    symbol: asset.symbol,
    display_symbol: asset.symbol,
    name: asset.name,
    asset_type: asset.asset_type,
    exchange: asset.exchange,
    currency: asset.currency,
    latest_price: asset.latest_price,
    source: "local",
    source_label: "Local asset",
    verified: true,
    broker_ticker: null,
  };
}

function normalizeSymbol(value: string) {
  return value.trim().toUpperCase();
}

function deriveQuantity(amount: string | number, price: number) {
  const numericAmount = typeof amount === "number" ? amount : Number(amount || 0);
  if (!(numericAmount > 0) || !(price > 0)) return 0;
  return numericAmount / price;
}

function parseOptional(value: string) {
  if (!value.trim()) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function round(value: number) {
  return Math.round(value * 10_000) / 10_000;
}

function formatInterval(seconds?: number | null) {
  const safeSeconds = Math.max(Number(seconds || 300), 60);
  if (safeSeconds < 120) return "1 minute";
  const minutes = Math.round(safeSeconds / 60);
  return `${minutes} minutes`;
}

function toggleListValue(list: string[], value: string, enabled: boolean) {
  if (enabled) return Array.from(new Set([...list, value]));
  return list.filter((item) => item !== value);
}

function defaultReplayStart() {
  const date = new Date();
  date.setDate(date.getDate() - 30);
  return toDatetimeLocal(date);
}

function defaultReplayEnd() {
  return toDatetimeLocal(new Date());
}

function toDatetimeLocal(date: Date) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}
