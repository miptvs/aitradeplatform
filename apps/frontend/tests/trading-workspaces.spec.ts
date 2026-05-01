import { expect, test } from "@playwright/test";

const now = new Date("2026-04-30T12:00:00Z").toISOString();

test.beforeEach(async ({ page }) => {
  await page.route("http://localhost:8000/api/v1/simulation/workspace**", async (route) => {
    await route.fulfill({ json: workspacePayload("simulation") });
  });
  await page.route("http://localhost:8000/api/v1/live/workspace", async (route) => {
    await route.fulfill({ json: workspacePayload("live") });
  });
  await page.route("http://localhost:8000/api/v1/simulation/replay-runs", async (route) => {
    await route.fulfill({ json: replayRunsPayload() });
  });
  await page.route("http://localhost:8000/api/v1/signals/**/trace", async (route) => {
    await route.fulfill({ json: signalTracePayload() });
  });
});

test("simulation page loads model comparison, replay scaffold, sell/short signals, and trace dialog", async ({ page }) => {
  await page.goto("/simulation");

  await expect(page.getByRole("heading", { name: "Simulation trading workspace" })).toBeVisible();
  await expect(page.getByText("Model account comparison")).toBeVisible();
  await expect(page.getByText("Replay / Backtest scaffold")).toBeVisible();
  await expect(page.getByText("Sell", { exact: true })).toBeVisible();
  await expect(page.getByText("Short", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "View trace" }).first().click();
  await expect(page.getByText("Decision trail")).toBeVisible();
});

test("live page renders disconnected Trading212 state and blocked automation explanation", async ({ page }) => {
  await page.goto("/live");

  await expect(page.getByRole("heading", { name: "Live trading workspace" })).toBeVisible();
  await expect(page.getByText("Trading212 not connected").first()).toBeVisible();
  await page.getByRole("button", { name: /Automation controls/ }).click();
  await expect(page.getByText("No live model selected")).toBeVisible();
  await expect(page.getByText("Live automation may use exactly one configured live provider/model")).toBeVisible();
});

function workspacePayload(mode: "simulation" | "live") {
  const simulation = mode === "simulation";
  return {
    mode,
    account: {
      mode,
      account_id: simulation ? "sim-openai" : null,
      account_label: simulation ? "OpenAI Simulation" : "No live broker configured",
      broker_type: simulation ? "simulation" : null,
      status: simulation ? "ok" : "disconnected",
      base_currency: "USD",
      total_value: simulation ? 10_250 : 0,
      total_cash: simulation ? 8_000 : 0,
      cash_available: simulation ? 8_000 : 0,
      available_to_trade_cash: simulation ? 6_000 : 0,
      cash_reserve_percent: 0.2,
      cash_reserve_amount: simulation ? 2_050 : 0,
      equity: simulation ? 2_250 : 0,
      realized_pnl: 120,
      unrealized_pnl: 130,
      open_positions_count: 1,
      active_orders_count: 0,
      total_trades_count: 4,
      safety_message: simulation
        ? "Simulation mirrors the live workflow but uses virtual cash, fees, and fills."
        : "Trading212 not connected. Live balances are hidden until a real broker sync succeeds.",
      live_execution_enabled: false,
      manual_position_supported: true,
      metadata: { supports_execution: false, short_supported: false },
    },
    automation: {
      id: `${mode}-automation`,
      mode,
      name: `${mode} automation`,
      enabled: true,
      automation_enabled: false,
      scheduled_execution_enabled: false,
      execution_interval_seconds: 300,
      inherit_from_live: false,
      effective_source_mode: mode,
      approval_mode: "semi_automatic",
      allowed_strategy_slugs: [],
      tradable_actions: ["buy", "sell", "close_long", "reduce_long"],
      allowed_provider_types: simulation ? ["openai_simulation"] : [],
      confidence_threshold: 0.58,
      default_order_notional: 100,
      stop_loss_pct: 0.03,
      take_profit_pct: 0.06,
      trailing_stop_pct: 0.02,
      max_orders_per_run: 1,
      risk_profile: "balanced",
      notes: null,
      last_run_at: null,
      last_scheduled_run_at: null,
      next_scheduled_run_at: null,
      last_run_status: null,
      last_run_message: null,
      config_json: simulation ? {} : { live_model_provider_type: null },
    },
    positions: [],
    orders: [],
    trades: [],
    signals: [
      signal("sig-sell", "SELL", "sell"),
      signal("sig-short", "SHORT", "short"),
    ],
    recommendations: [],
    alerts: [],
    assets: [
      { id: "asset-1", symbol: "AAPL", name: "Apple Inc.", asset_type: "stock", sector: "Technology", exchange: "NASDAQ", currency: "USD", is_active: true, latest_price: 190 },
      { id: "asset-2", symbol: "TSLA", name: "Tesla Inc.", asset_type: "stock", sector: "Consumer", exchange: "NASDAQ", currency: "USD", is_active: true, latest_price: 160 },
    ],
    strategies: [
      { id: "strat-1", name: "Trend Following", slug: "trend-following", category: "technical", description: "Trend", enabled: true, config_json: {} },
      { id: "strat-2", name: "Blended", slug: "blended", category: "hybrid", description: "Blend", enabled: true, config_json: {} },
    ],
    controls: simulation
      ? {
          active_simulation_account_id: "sim-openai",
          simulation_accounts: [
            {
              id: "sim-openai",
              name: "OpenAI Simulation",
              provider_type: "openai_simulation",
              model_name: "gpt-5-mini",
              starting_cash: 10000,
              cash_balance: 8000,
              reserved_cash: 2050,
              available_to_trade_cash: 6000,
              portfolio_value: 10250,
              total_return: 0.025,
              win_rate: 0.5,
              profit_factor: 1.2,
              max_drawdown: -0.01,
              trade_count: 4,
              rejected_trade_count: 1,
              invalid_signal_rate: 0,
              fees_bps: 5,
              slippage_bps: 2,
              latency_ms: 50,
              short_enabled: true,
              short_borrow_fee_bps: 0,
              short_margin_requirement: 1.5,
              partial_fill_ratio: 1,
              enforce_market_hours: false,
              is_active: true,
              reset_count: 0,
            },
          ],
        }
      : { live_model_provider_type: null, broker_accounts: [] },
  };
}

function signal(id: string, label: string, action: string) {
  return {
    id,
    asset_id: "asset-1",
    symbol: label === "SELL" ? "AAPL" : "TSLA",
    asset_name: label === "SELL" ? "Apple Inc." : "Tesla Inc.",
    strategy_name: "Blended",
    strategy_slug: "blended",
    action,
    confidence: 0.81,
    status: "candidate",
    occurred_at: now,
    ai_rationale: `${label} candidate for smoke test.`,
    suggested_entry: 100,
    suggested_stop_loss: 105,
    suggested_take_profit: 90,
    estimated_risk_reward: 2,
    provider_type: "openai_simulation",
    model_name: "gpt-5-mini",
    indicators_json: {},
    related_news_ids: [],
    related_event_ids: [],
    mode: "shared",
    source_kind: "agent",
    metadata_json: { trade_intent: action === "short" ? "open_short" : "bearish_watch", preferred_strategy: "blended" },
    signal_flavor: "technical+ai",
    fresh_news_used: false,
    lane_statuses: { simulation: "candidate", live: "candidate" },
  };
}

function signalTracePayload() {
  const rootSignal = signal("sig-sell", "SELL", "sell");
  return {
    signal: { ...rootSignal, related_news: [], related_events: [] },
    entrypoint: { type: "signal", id: "sig-sell", label: "sell" },
    summary: { mode: "shared", execution_mode: "signal-only", signal_linked: true, strategy: "blended", provider_type: "openai_simulation", model_name: "gpt-5-mini", orders_count: 0, trades_count: 0, positions_count: 0 },
    risk_checks: [],
    stop_history: [],
    evaluations: [],
    orders: [],
    positions: [],
    trades: [],
    audit_logs: [],
  };
}

function replayRunsPayload() {
  return [
    {
      id: "replay-1",
      name: "Replay scaffold",
      status: "completed",
      started_at: now,
      completed_at: now,
      date_start: "2026-04-01T00:00:00Z",
      date_end: now,
      starting_cash: 10000,
      fees_bps: 5,
      slippage_bps: 2,
      cash_reserve_percent: 0.2,
      short_enabled: true,
      selected_models: ["openai_simulation"],
      symbols: ["AAPL", "TSLA"],
      config_json: { execution_model: "scaffold" },
      notes: "Smoke",
      created_at: now,
      updated_at: now,
      results: [
        {
          id: "result-1",
          replay_run_id: "replay-1",
          provider_type: "openai_simulation",
          model_name: "gpt-5-mini",
          status: "completed",
          cash: 10000,
          portfolio_value: 10100,
          realized_pnl: 100,
          unrealized_pnl: 0,
          total_return: 0.01,
          max_drawdown: -0.01,
          sharpe: 1.1,
          sortino: 1.4,
          win_rate: 0.5,
          profit_factor: 1.2,
          average_holding_time_minutes: 60,
          turnover: 0.1,
          trades: 2,
          rejected_trades: 1,
          invalid_signals: 0,
          useful_signal_rate: 0.5,
          latency_ms: 500,
          model_cost: null,
          metrics_json: { scaffold: true },
        },
      ],
    },
  ];
}
