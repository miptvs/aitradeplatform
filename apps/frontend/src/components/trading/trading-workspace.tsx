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
import { formatCurrency, formatPct, formatQuantity } from "@/lib/utils";
import type {
  Asset,
  AssetSearchResult,
  Order,
  Position,
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
  const [manualTradingOpen, setManualTradingOpen] = useState(false);
  const [selectedSimulationAccountId, setSelectedSimulationAccountId] = useState("");
  const workspaceState = useApi<TradingWorkspaceData>(
    () => (mode === "live" ? api.getLiveWorkspace() : api.getSimulationWorkspace(selectedSimulationAccountId || undefined)),
    [mode, selectedSimulationAccountId]
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
  const [recommendationBusyId, setRecommendationBusyId] = useState<string | null>(null);
  const [brokerSyncingId, setBrokerSyncingId] = useState<string | null>(null);
  const provenance = useProvenanceTrace();

  const workspaceData = workspaceState.data;
  const localAssetDefaults = useMemo(() => (workspaceData?.assets || []).slice(0, 8).map(toLocalSearchResult), [workspaceData?.assets]);
  const providerOptions = useMemo(
    () =>
      Array.from(
        new Set([
          mode === "simulation" ? workspace.simulationProviderType : workspace.liveProviderType,
          workspace.signalProviderType,
          "manual",
        ])
      ),
    [mode, workspace.liveProviderType, workspace.signalProviderType, workspace.simulationProviderType]
  );

  useEffect(() => {
    if (mode !== "simulation" || !workspaceData) return;
    const controlAccountId = String((workspaceData.controls.active_simulation_account_id as string | undefined) || "");
    if (controlAccountId && !selectedSimulationAccountId) {
      setSelectedSimulationAccountId(controlAccountId);
    }
  }, [mode, selectedSimulationAccountId, workspaceData]);

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
  const simulationAccounts = (workspaceData.controls.simulation_accounts as Array<Record<string, unknown>> | undefined) || [];
  const brokerAccounts = (workspaceData.controls.broker_accounts as Array<Record<string, unknown>> | undefined) || [];
  const closePreviewPct = closePercent ? Number(closePercent) : 100;
  const closePreviewQty = closeDialogPosition ? (closeDialogPosition.quantity * closePreviewPct) / 100 : 0;

  function loadRecommendationIntoTicket(recommendation: TradingRecommendation) {
    if (!workspaceData || !automationForm) return;
    const asset = workspaceData.assets.find((item) => item.id === recommendation.asset_id);
    const suggestedEntry = recommendation.suggested_entry || asset?.latest_price || 0;
    const trailingStop =
      automationForm.trailing_stop_pct && suggestedEntry > 0 ? String(round(suggestedEntry * automationForm.trailing_stop_pct)) : "";
    const derivedQuantityFromNotional =
      automationForm.default_order_notional > 0 && suggestedEntry > 0
        ? String(Math.round((automationForm.default_order_notional / suggestedEntry) * 1_000_000) / 1_000_000)
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
      amount: String(automationForm.default_order_notional),
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
        message: `${result.message} Account: ${result.account_message} Positions: ${result.positions_message} Orders: ${result.orders_message}`,
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
      <RiskBanner alerts={workspaceData.alerts} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatsCard label="Account Value" value={workspaceData.account.total_value} />
        <StatsCard label="Cash Available" value={workspaceData.account.cash_available} />
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
            setBanner({ tone: "success", message: "Simulation account reset to its configured clean state." });
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
            positions={workspaceData.positions}
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
                <div className="mt-2">Current quantity: {formatQuantity(closeDialogPosition.quantity, 6)}</div>
                <div className="mt-1">Preview close size: {formatQuantity(closePreviewQty || closeDialogPosition.quantity, 6)}</div>
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
  const [draft, setDraft] = useState({ starting_cash: 1000, fees_bps: 5, slippage_bps: 2, latency_ms: 50 });

  useEffect(() => {
    if (mode !== "simulation") return;
    const current = simulationAccounts.find((account) => account.id === selectedSimulationAccountId);
    if (!current) return;
    setDraft({
      starting_cash: Number(current.starting_cash || 1000),
      fees_bps: Number(current.fees_bps || 0),
      slippage_bps: Number(current.slippage_bps || 0),
      latency_ms: Number(current.latency_ms || 0),
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
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={() => onSaveSimulationSettings(draft)} className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-500/20">
              Save sim settings
            </button>
            <button type="button" onClick={onResetSimulation} className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 hover:bg-amber-500/20">
              Reset simulation account
            </button>
          </div>
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
                <SummaryChip label="Last sync status" value={String(account.last_sync_status || "Never run")} />
                <SummaryChip label="Last sync time" value={String(account.last_sync_completed_at || account.last_sync_started_at || "n/a")} />
              </div>
              {account.last_sync_message ? <div className="mt-3 text-xs text-slate-400">{String(account.last_sync_message)}</div> : null}
            </div>
          ))}
          {!brokerAccounts.length ? <div className="text-sm text-slate-500">No broker account is configured yet.</div> : null}
        </div>
      )}
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
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
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
        <CheckList
          title="Allowed providers"
          description="Keep automation scoped to the provider/model profiles you trust for this lane."
          items={providerOptions.map((provider) => ({ value: provider, label: provider }))}
          value={automationForm.allowed_provider_types}
          onChange={(next) => onChange((current) => (current ? { ...current, allowed_provider_types: next } : current))}
          disabled={inheritsLive}
        />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <ToggleField
          label="Allow buys"
          checked={automationForm.tradable_actions.includes("buy")}
          onChange={(checked) => onChange((current) => (current ? { ...current, tradable_actions: toggleListValue(current.tradable_actions, "buy", checked) } : current))}
          disabled={inheritsLive}
        />
        <ToggleField
          label="Allow sells"
          checked={automationForm.tradable_actions.includes("sell")}
          onChange={(checked) => onChange((current) => (current ? { ...current, tradable_actions: toggleListValue(current.tradable_actions, "sell", checked) } : current))}
          disabled={inheritsLive}
        />
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

function formatDateTime(value?: string | null) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not scheduled";
  return date.toLocaleString();
}

function toggleListValue(list: string[], value: string, enabled: boolean) {
  if (enabled) return Array.from(new Set([...list, value]));
  return list.filter((item) => item !== value);
}
