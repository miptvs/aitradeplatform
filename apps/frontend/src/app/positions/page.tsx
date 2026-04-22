"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { PositionManagementTable } from "@/components/trading/position-management-table";
import { Dialog } from "@/components/ui/dialog";
import { HelpTooltip } from "@/components/ui/help-tooltip";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { formatCurrency, formatQuantity } from "@/lib/utils";
import type { Asset, AssetSearchResult, Position } from "@/types";

type SizingMode = "amount" | "quantity";

export default function PositionsPage() {
  const state = useApi(async () => {
    const [positions, assets, strategies, simulationAccounts, brokerAccounts] = await Promise.all([
      api.getPositions(),
      api.getAssets(),
      api.getStrategies(),
      api.getSimulationAccounts(),
      api.getBrokerAccounts(),
    ]);
    return { positions, assets, strategies, simulationAccounts, brokerAccounts };
  });

  const [filterMode, setFilterMode] = useState<"all" | "live" | "simulation">("all");
  const [message, setMessage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<AssetSearchResult[]>([]);
  const [searchMessage, setSearchMessage] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [detailPosition, setDetailPosition] = useState<Position | null>(null);
  const [stopPosition, setStopPosition] = useState<Position | null>(null);
  const [closePosition, setClosePosition] = useState<Position | null>(null);
  const [closePercent, setClosePercent] = useState("");
  const [stopForm, setStopForm] = useState({ stop_loss: "", take_profit: "", trailing_stop: "", notes: "" });
  const [form, setForm] = useState({
    mode: "simulation",
    simulation_account_id: "",
    broker_account_id: "",
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
    strategy_name: "trend-following",
    stop_loss: "",
    take_profit: "",
    trailing_stop: "",
    notes: "",
  });

  const localDefaults = useMemo(() => (state.data?.assets || []).slice(0, 8).map(toLocalSearchResult), [state.data?.assets]);
  const filteredPositions = useMemo(
    () => (state.data?.positions || []).filter((position) => filterMode === "all" || position.mode === filterMode),
    [filterMode, state.data?.positions]
  );
  const selectedAsset = useMemo(() => {
    if (!state.data) return null;
    return state.data.assets.find((asset) => asset.id === form.asset_id || asset.symbol === form.asset_symbol) || null;
  }, [form.asset_id, form.asset_symbol, state.data]);

  useEffect(() => {
    if (!state.data?.simulationAccounts.length || form.simulation_account_id) return;
    setForm((current) => ({ ...current, simulation_account_id: state.data?.simulationAccounts[0].id || "" }));
  }, [form.simulation_account_id, state.data?.simulationAccounts]);

  useEffect(() => {
    const normalized = searchQuery.trim().toUpperCase();
    if (!normalized) {
      setSearchResults(localDefaults);
      setSearchMessage("Showing local assets already known to this workspace.");
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
  }, [localDefaults, searchQuery]);

  useEffect(() => {
    if (!selectedAsset) return;
    setForm((current) => ({
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

  if (state.loading || !state.data) return <div className="text-sm text-slate-400">Loading positions...</div>;
  if (state.error) return <div className="text-sm text-rose-300">Positions failed to load: {state.error}</div>;

  const entryPrice = Number(form.avg_entry_price || selectedAsset?.latest_price || 0);
  const derivedQuantity = form.sizing_mode === "amount" ? deriveQuantity(form.amount, entryPrice) : Number(form.quantity || 0);
  const estimatedNotional = entryPrice > 0 ? entryPrice * derivedQuantity : 0;
  const closePreviewPct = closePercent ? Number(closePercent) : 100;
  const closePreviewQty = closePosition ? (closePosition.quantity * closePreviewPct) / 100 : 0;

  return (
    <div className="space-y-6">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Positions</div>
        <h1 className="mt-1 text-2xl font-semibold text-slate-100">Positions ledger and stop management</h1>
        <div className="mt-2 text-sm text-slate-400">Use the compact action menu on each row to manage stops, manual overrides, and partial closes without cluttering the whole table.</div>
      </div>

      {message ? <div className="rounded-2xl border border-border bg-panel/90 px-4 py-3 text-sm text-slate-200 shadow-panel">{message}</div> : null}

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Create manual position</div>
          <div className="mt-1 text-sm text-slate-400">
            This is for mirroring an existing fill or seeding a starting line before automation takes over. Small budgets and fractional quantities are supported.
          </div>
          <form
            className="mt-4 space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              try {
                await api.createPosition({
                  asset_id: form.asset_id || null,
                  asset_symbol: form.asset_symbol || null,
                  asset_name: form.asset_name || form.asset_symbol,
                  asset_type: form.asset_type,
                  currency: form.currency,
                  exchange: form.exchange || null,
                  mode: form.mode,
                  quantity: derivedQuantity,
                  avg_entry_price: Number(form.avg_entry_price),
                  current_price: Number(form.current_price || form.avg_entry_price),
                  strategy_name: form.strategy_name,
                  stop_loss: parseOptional(form.stop_loss),
                  take_profit: parseOptional(form.take_profit),
                  trailing_stop: parseOptional(form.trailing_stop),
                  notes: form.notes || null,
                  simulation_account_id: form.mode === "simulation" ? form.simulation_account_id : null,
                  broker_account_id: form.mode === "live" ? form.broker_account_id || null : null,
                  tags: ["manual", form.mode],
                });
                setMessage(`Manual ${form.mode} position added.`);
                setForm((current) => ({
                  ...current,
                  asset_id: "",
                  asset_symbol: "",
                  asset_name: "",
                  amount: "100",
                  quantity: "",
                  avg_entry_price: "",
                  current_price: "",
                  stop_loss: "",
                  take_profit: "",
                  trailing_stop: "",
                  notes: "",
                }));
                setSearchQuery("");
                state.reload();
              } catch (error) {
                setMessage(error instanceof Error ? error.message : "Manual position creation failed.");
              }
            }}
          >
            <Field label={<HelpTooltip label="Ticker search" help="Search by ticker or name. Local assets are shown first, and broker-verified matches can appear when available." />}>
              <div className="space-y-2">
                <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search ticker" className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
                <div className="rounded-2xl border border-border bg-black/20 p-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Matches</div>
                  {searchLoading ? <div className="mt-2 text-sm text-slate-400">Searching...</div> : null}
                  {!searchLoading && searchResults.length ? (
                    <div className="mt-3 space-y-2">
                      {searchResults.map((result) => (
                        <button
                          key={result.key}
                          type="button"
                          onClick={() => {
                            setForm((current) => ({
                              ...current,
                              asset_id: result.asset_id || "",
                              asset_symbol: result.symbol,
                              asset_name: result.name,
                              asset_type: result.asset_type,
                              currency: result.currency,
                              exchange: result.exchange || "",
                            }));
                            setSearchQuery(result.symbol);
                          }}
                          className="flex w-full items-center justify-between rounded-xl border border-border px-3 py-3 text-left hover:bg-white/5"
                        >
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

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Mode">
                <select value={form.mode} onChange={(event) => setForm((current) => ({ ...current, mode: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
                  <option value="simulation">Simulation</option>
                  <option value="live">Live</option>
                </select>
              </Field>
              {form.mode === "simulation" ? (
                <Field label="Simulation account">
                  <select value={form.simulation_account_id} onChange={(event) => setForm((current) => ({ ...current, simulation_account_id: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
                    {state.data.simulationAccounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name}
                      </option>
                    ))}
                  </select>
                </Field>
              ) : (
                <Field label="Broker account">
                  <select value={form.broker_account_id} onChange={(event) => setForm((current) => ({ ...current, broker_account_id: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
                    <option value="">Auto-select enabled broker</option>
                    {state.data.brokerAccounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              <Field label="Sizing mode">
                <select value={form.sizing_mode} onChange={(event) => setForm((current) => ({ ...current, sizing_mode: event.target.value as SizingMode }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
                  <option value="amount">Amount</option>
                  <option value="quantity">Quantity</option>
                </select>
              </Field>
              <Field label={form.sizing_mode === "amount" ? "Amount" : "Quantity"}>
                <input
                  type="number"
                  step="0.0001"
                  value={form.sizing_mode === "amount" ? form.amount : form.quantity}
                  onChange={(event) =>
                    setForm((current) =>
                      current.sizing_mode === "amount" ? { ...current, amount: event.target.value } : { ...current, quantity: event.target.value }
                    )
                  }
                  className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100"
                />
              </Field>
              <Field label="Entry price">
                <input type="number" step="0.0001" value={form.avg_entry_price} onChange={(event) => setForm((current) => ({ ...current, avg_entry_price: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
              </Field>
              <Field label="Current price">
                <input type="number" step="0.0001" value={form.current_price} onChange={(event) => setForm((current) => ({ ...current, current_price: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
              </Field>
              <Field label="Strategy tag">
                <select value={form.strategy_name} onChange={(event) => setForm((current) => ({ ...current, strategy_name: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100">
                  {state.data.strategies.map((strategy) => (
                    <option key={strategy.id} value={strategy.slug}>
                      {strategy.name}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <Field label={<HelpTooltip label="Stop loss" help="Automatically closes the trade if price moves against you to this level." />}>
                <input type="number" step="0.0001" value={form.stop_loss} onChange={(event) => setForm((current) => ({ ...current, stop_loss: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
              </Field>
              <Field label={<HelpTooltip label="Take profit" help="Automatically closes the trade once the target profit price is reached." />}>
                <input type="number" step="0.0001" value={form.take_profit} onChange={(event) => setForm((current) => ({ ...current, take_profit: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
              </Field>
              <Field label={<HelpTooltip label="Trailing stop" help="Moves the stop upward as price rises, helping protect profits." />}>
                <input type="number" step="0.0001" value={form.trailing_stop} onChange={(event) => setForm((current) => ({ ...current, trailing_stop: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
              </Field>
            </div>

            <Field label="Notes">
              <textarea rows={3} value={form.notes} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>

            <div className="rounded-2xl border border-border bg-black/20 p-4 text-sm text-slate-300">
              Estimated quantity: <span className="font-semibold text-slate-100">{formatQuantity(derivedQuantity, 6)}</span>
              <br />
              Estimated notional: <span className="font-semibold text-slate-100">{formatCurrency(estimatedNotional, form.currency || "USD")}</span>
            </div>

            <button className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-500/20">Create position</button>
          </form>
        </section>

        <section className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Current positions</div>
              <div className="mt-1 text-sm text-slate-400">Filter the cross-book ledger, then use the row action menu for the next step.</div>
            </div>
            <div className="flex gap-2">
              {(["all", "simulation", "live"] as const).map((value) => (
                <button key={value} type="button" onClick={() => setFilterMode(value)} className={`rounded-full border px-3 py-2 text-xs uppercase tracking-[0.14em] ${filterMode === value ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-100" : "border-border text-slate-300 hover:bg-white/5"}`}>
                  {value}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-4">
            <PositionManagementTable
              positions={filteredPositions}
              emptyMessage="No positions match the current filter."
              onViewDetails={setDetailPosition}
              onEditStops={(position) => {
                setStopPosition(position);
                setStopForm({
                  stop_loss: position.stop_loss ? String(position.stop_loss) : "",
                  take_profit: position.take_profit ? String(position.take_profit) : "",
                  trailing_stop: position.trailing_stop ? String(position.trailing_stop) : "",
                  notes: position.notes || "",
                });
              }}
              onClose={(position) => {
                setClosePosition(position);
                setClosePercent("");
              }}
              onMarkOverride={async (position) => {
                await api.updatePosition(position.id, { manual_override: true });
                setMessage(`${position.symbol} marked as manual override.`);
                state.reload();
              }}
            />
          </div>
        </section>
      </div>

      <Dialog
        open={Boolean(stopPosition)}
        title="Edit stop settings"
        description="Stops are managed in a modal here so the ledger stays compact and readable."
        actions={<button type="button" onClick={() => setStopPosition(null)} className="rounded-xl border border-border px-3 py-2 text-sm text-slate-300 hover:bg-white/5">Close</button>}
      >
        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!stopPosition) return;
            await api.updatePosition(stopPosition.id, {
              stop_loss: parseOptional(stopForm.stop_loss),
              take_profit: parseOptional(stopForm.take_profit),
              trailing_stop: parseOptional(stopForm.trailing_stop),
              notes: stopForm.notes || null,
              manual_override: true,
            });
            setMessage(`Stop settings updated for ${stopPosition.symbol}.`);
            setStopPosition(null);
            state.reload();
          }}
        >
          <div className="grid gap-4 md:grid-cols-3">
            <Field label="Stop loss">
              <input type="number" step="0.0001" value={stopForm.stop_loss} onChange={(event) => setStopForm((current) => ({ ...current, stop_loss: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Take profit">
              <input type="number" step="0.0001" value={stopForm.take_profit} onChange={(event) => setStopForm((current) => ({ ...current, take_profit: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
            <Field label="Trailing stop">
              <input type="number" step="0.0001" value={stopForm.trailing_stop} onChange={(event) => setStopForm((current) => ({ ...current, trailing_stop: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
            </Field>
          </div>
          <Field label="Notes">
            <textarea rows={3} value={stopForm.notes} onChange={(event) => setStopForm((current) => ({ ...current, notes: event.target.value }))} className="rounded-xl border border-border bg-slate-950 px-3 py-2 text-slate-100" />
          </Field>
          <button className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 hover:bg-emerald-500/20">Save stops</button>
        </form>
      </Dialog>

      <Dialog
        open={Boolean(closePosition)}
        title="Close position"
        description="Enter a percentage to close part of the line. Leave it blank to close the whole position."
        actions={<button type="button" onClick={() => setClosePosition(null)} className="rounded-xl border border-border px-3 py-2 text-sm text-slate-300 hover:bg-white/5">Close</button>}
      >
        <div className="space-y-4">
          <div className="rounded-2xl border border-border bg-black/20 p-4 text-sm text-slate-300">
            {closePosition ? (
              <>
                <div className="font-semibold text-slate-100">{closePosition.symbol}</div>
                <div className="mt-2">Current quantity: {formatQuantity(closePosition.quantity, 6)}</div>
                <div className="mt-1">Preview close size: {formatQuantity(closePreviewQty || closePosition.quantity, 6)}</div>
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
              if (!closePosition) return;
              await api.closePosition(closePosition.id, { closePercent: closePercent ? Number(closePercent) : undefined });
              setMessage(`${closePosition.symbol} close request applied.`);
              setClosePosition(null);
              state.reload();
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
        description="Inspect the full position metadata without bloating the main table."
        actions={<button type="button" onClick={() => setDetailPosition(null)} className="rounded-xl border border-border px-3 py-2 text-sm text-slate-300 hover:bg-white/5">Close</button>}
      >
        {detailPosition ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Detail label="Symbol" value={`${detailPosition.symbol} · ${detailPosition.asset_name}`} />
            <Detail label="Mode" value={detailPosition.mode} />
            <Detail label="Quantity" value={formatQuantity(detailPosition.quantity, 6)} />
            <Detail label="Average entry" value={formatCurrency(detailPosition.avg_entry_price, detailPosition.asset_currency)} />
            <Detail label="Current price" value={formatCurrency(detailPosition.current_price, detailPosition.asset_currency)} />
            <Detail label="Stops" value={`SL ${detailPosition.stop_loss || "-"} · TP ${detailPosition.take_profit || "-"} · TR ${detailPosition.trailing_stop || "-"}`} />
            <Detail label="Strategy" value={detailPosition.strategy_name || "-"} />
            <Detail label="Notes" value={detailPosition.notes || "-"} />
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}

function Field({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <label className="grid gap-2 text-sm text-slate-300">
      <div>{label}</div>
      {children}
    </label>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-black/20 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-100">{value}</div>
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

function deriveQuantity(amount: string, entryPrice: number) {
  const numericAmount = Number(amount || 0);
  if (!(numericAmount > 0) || !(entryPrice > 0)) return 0;
  return numericAmount / entryPrice;
}

function parseOptional(value: string) {
  if (!value.trim()) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}
