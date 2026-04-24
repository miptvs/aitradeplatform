export interface ProviderConfig {
  id: string;
  provider_type: string;
  adapter_type: string;
  vendor_key: string;
  vendor_name: string;
  deployment_scope: "local" | "remote" | string;
  trading_mode: "simulation" | "live" | string;
  mode_label: string;
  name: string;
  description: string;
  enabled: boolean;
  base_url: string;
  default_model?: string | null;
  temperature: number;
  max_tokens: number;
  context_window: number;
  tool_calling_enabled: boolean;
  reasoning_mode?: string | null;
  reasoning_modes: string[];
  task_defaults: Record<string, string>;
  settings_json: Record<string, unknown>;
  suggested_models: string[];
  supports_api_key: boolean;
  has_secret: boolean;
  last_health_status?: string | null;
  last_health_message?: string | null;
  last_checked_at?: string | null;
}

export interface Asset {
  id: string;
  symbol: string;
  name: string;
  asset_type: string;
  sector?: string | null;
  exchange?: string | null;
  currency: string;
  is_active: boolean;
  latest_price?: number | null;
}

export interface AssetSearchResult {
  key: string;
  asset_id?: string | null;
  symbol: string;
  display_symbol: string;
  name: string;
  asset_type: string;
  exchange?: string | null;
  currency: string;
  latest_price?: number | null;
  source: string;
  source_label: string;
  verified: boolean;
  broker_ticker?: string | null;
}

export interface AssetSearchResponse {
  query: string;
  validation_source?: string | null;
  validation_status: string;
  message?: string | null;
  results: AssetSearchResult[];
}

export interface ProviderHealth {
  provider_type: string;
  vendor_name?: string;
  trading_mode?: string;
  status: string;
  message: string;
  latency_ms?: number | null;
}

export interface Position {
  id: string;
  asset_id: string;
  symbol: string;
  asset_name: string;
  signal_id?: string | null;
  mode: string;
  manual: boolean;
  manual_override: boolean;
  strategy_name?: string | null;
  provider_type?: string | null;
  model_name?: string | null;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  stop_loss?: number | null;
  take_profit?: number | null;
  trailing_stop?: number | null;
  unrealized_pnl: number;
  realized_pnl: number;
  notes?: string | null;
  tags: string[];
  status: string;
  asset_currency?: string;
}

export interface Order {
  id: string;
  asset_id: string;
  symbol: string;
  asset_name: string;
  signal_id?: string | null;
  position_id?: string | null;
  mode: string;
  side: string;
  order_type: string;
  quantity: number;
  requested_price?: number | null;
  filled_price?: number | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  trailing_stop?: number | null;
  fees: number;
  status: string;
  manual: boolean;
  strategy_name?: string | null;
  provider_type?: string | null;
  model_name?: string | null;
  entry_reason?: string | null;
  exit_reason?: string | null;
  rejection_reason?: string | null;
  audit_context: Record<string, unknown>;
  created_at: string;
  executed_at?: string | null;
}

export interface Trade {
  id: string;
  asset_id: string;
  symbol: string;
  asset_name: string;
  order_id?: string | null;
  position_id?: string | null;
  signal_id?: string | null;
  mode: string;
  manual: boolean;
  side: string;
  quantity: number;
  price: number;
  fees: number;
  realized_pnl: number;
  strategy_name?: string | null;
  provider_type?: string | null;
  model_name?: string | null;
  entry_reason?: string | null;
  exit_reason?: string | null;
  executed_at: string;
}

export interface Signal {
  id: string;
  asset_id: string;
  symbol: string;
  asset_name: string;
  strategy_name?: string | null;
  strategy_slug?: string | null;
  action: string;
  confidence: number;
  status: string;
  occurred_at: string;
  ai_rationale?: string | null;
  suggested_entry?: number | null;
  suggested_stop_loss?: number | null;
  suggested_take_profit?: number | null;
  estimated_risk_reward?: number | null;
  provider_type?: string | null;
  model_name?: string | null;
  indicators_json: Record<string, unknown>;
  related_news_ids: string[];
  related_event_ids: string[];
  mode: string;
  source_kind: string;
  metadata_json: Record<string, unknown>;
  signal_flavor: string;
  fresh_news_used: boolean;
  lane_statuses: Record<string, string>;
}

export interface SignalEvaluation {
  id: string;
  signal_id: string;
  approved: boolean;
  evaluator: string;
  reason?: string | null;
  risk_score?: number | null;
  expected_return?: number | null;
  realized_return?: number | null;
  outcome?: string | null;
  created_at: string;
}

export interface SignalDetail extends Signal {
  strategy_id?: string | null;
  strategy_slug?: string | null;
  related_news: NewsArticle[];
  related_events: ExtractedEvent[];
}

export interface AuditLog {
  id: string;
  actor: string;
  action: string;
  target_type: string;
  target_id?: string | null;
  status: string;
  mode?: string | null;
  details_json: Record<string, unknown>;
  occurred_at: string;
}

export interface SignalTrace {
  signal?: SignalDetail | null;
  entrypoint: Record<string, unknown>;
  summary: Record<string, unknown>;
  risk_checks: Array<Record<string, unknown>>;
  stop_history: Array<Record<string, unknown>>;
  evaluations: SignalEvaluation[];
  orders: Order[];
  positions: Position[];
  trades: Trade[];
  audit_logs: AuditLog[];
}

export interface NewsArticle {
  id: string;
  title: string;
  source: string;
  url: string;
  published_at: string;
  summary?: string | null;
  sentiment?: string | null;
  impact_score?: number | null;
  affected_symbols: string[];
  provider_type?: string | null;
  model_name?: string | null;
  analysis_metadata?: Record<string, unknown>;
}

export interface NewsFeedDiagnostic {
  feed_url: string;
  feed_label: string;
  status: string;
  fetched_count: number;
  added_count: number;
  duplicate_count: number;
  date_skipped_count: number;
  parse_error_count: number;
  sample_titles: string[];
  latest_seen_published_at?: string | null;
  error?: string | null;
}

export interface NewsRefreshDiagnostics {
  message: string;
  articles_added: number;
  feeds_checked: number;
  feeds_failed: number;
  duplicates_skipped: number;
  date_skipped: number;
  latest_article_id?: string | null;
  cutoff: string;
  latest_seen_published_at?: string | null;
  force_refresh: boolean;
  last_successful_fetch_time?: string | null;
  errors: string[];
  feed_reports: NewsFeedDiagnostic[];
}

export interface ExtractedEvent {
  id: string;
  news_article_id?: string | null;
  event_type: string;
  symbol?: string | null;
  confidence: number;
  impact_score: number;
  summary: string;
}

export interface SimulationAccount {
  id: string;
  name: string;
  starting_cash: number;
  cash_balance: number;
  fees_bps: number;
  slippage_bps: number;
  latency_ms: number;
  is_active: boolean;
  reset_count: number;
}

export interface SignalRefreshResult {
  provider_type: string;
  status: "success" | "noop" | "blocked" | "error" | string;
  created_signal_ids: string[];
  created_count: number;
  message: string;
  detail?: string | null;
  market_report: Record<string, unknown>;
  news_report: Record<string, unknown>;
}

export interface SimulationSummary {
  account: SimulationAccount;
  equity_curve: { timestamp: string; value: number }[];
  open_positions: number;
  total_trades: number;
  hypothetical_pnl: number;
  latest_orders: Order[];
}

export interface PortfolioSummary {
  total_portfolio_value: number;
  cash_available: number;
  realized_pnl: number;
  unrealized_pnl: number;
  daily_return: number;
  weekly_return: number;
  monthly_return: number;
  win_rate: number;
  open_positions_count: number;
  closed_trades_count: number;
  best_performer: { symbol: string; pnl: number };
  worst_performer: { symbol: string; pnl: number };
  risk_exposure_summary: Record<string, unknown>;
  broker_connection_status: Record<string, string>;
  provider_status: Record<string, string>;
  automation_status: Record<string, string>;
}

export interface PortfolioSnapshot {
  id: string;
  mode: string;
  timestamp: string;
  total_value: number;
  cash: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  daily_return: number;
  weekly_return: number;
  monthly_return: number;
  exposure_json: Record<string, number>;
}

export interface AnalyticsOverview {
  total_return: number;
  realized_return: number;
  unrealized_return: number;
  annualized_return: number;
  win_rate: number;
  average_win: number;
  average_loss: number;
  payoff_ratio: number;
  profit_factor: number;
  max_drawdown: number;
  sharpe: number;
  sortino: number;
  performance_by_symbol: { name: string; value: number }[];
  performance_by_strategy: { name: string; value: number }[];
  performance_by_provider: { name: string; value: number }[];
  confidence_correlation: number;
}

export interface SimulationVsLive {
  live_return: number;
  simulation_return: number;
  delta_return: number;
}

export interface RiskRule {
  id: string;
  name: string;
  scope: string;
  rule_type: string;
  enabled: boolean;
  auto_close: boolean;
  description?: string | null;
  config_json: Record<string, unknown>;
}

export interface StrategyOption {
  id: string;
  name: string;
  slug: string;
  category: string;
  description: string;
  enabled: boolean;
  config_json: Record<string, unknown>;
}

export interface TradingAutomationProfile {
  id: string;
  mode: string;
  name: string;
  enabled: boolean;
  automation_enabled: boolean;
  scheduled_execution_enabled: boolean;
  execution_interval_seconds: number;
  inherit_from_live: boolean;
  effective_source_mode: string;
  approval_mode: "manual_only" | "semi_automatic" | "fully_automatic" | string;
  allowed_strategy_slugs: string[];
  tradable_actions: string[];
  allowed_provider_types: string[];
  confidence_threshold: number;
  default_order_notional: number;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  trailing_stop_pct?: number | null;
  max_orders_per_run: number;
  risk_profile: string;
  notes?: string | null;
  last_run_at?: string | null;
  last_scheduled_run_at?: string | null;
  next_scheduled_run_at?: string | null;
  last_run_status?: string | null;
  last_run_message?: string | null;
  config_json: Record<string, unknown>;
}

export interface TradingAccountSummary {
  mode: string;
  account_id?: string | null;
  account_label: string;
  broker_type?: string | null;
  status: string;
  base_currency: string;
  total_value: number;
  cash_available: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  open_positions_count: number;
  active_orders_count: number;
  total_trades_count: number;
  safety_message: string;
  live_execution_enabled: boolean;
  manual_position_supported: boolean;
  metadata: Record<string, unknown>;
}

export interface TradingWorkspace {
  mode: string;
  account: TradingAccountSummary;
  automation: TradingAutomationProfile;
  positions: Position[];
  orders: Order[];
  trades: Trade[];
  signals: Signal[];
  recommendations: TradingRecommendation[];
  alerts: Alert[];
  assets: Asset[];
  strategies: StrategyOption[];
  controls: Record<string, unknown>;
}

export interface AutomationDecision {
  signal_id: string;
  symbol: string;
  action: string;
  confidence: number;
  strategy_slug?: string | null;
  provider_type?: string | null;
  outcome: string;
  reason: string;
  order_id?: string | null;
}

export interface AutomationRunResult {
  mode: string;
  status: string;
  message: string;
  processed_signals: number;
  submitted_orders: number;
  approved_recommendations: number;
  rejected_signals: number;
  decisions: AutomationDecision[];
}

export interface PositionAction {
  key: string;
  label: string;
  description: string;
  destructive: boolean;
  requires_confirmation: boolean;
}

export interface TradingRecommendation {
  signal_id: string;
  asset_id: string;
  symbol: string;
  asset_name: string;
  action: string;
  confidence: number;
  strategy_slug?: string | null;
  provider_type?: string | null;
  model_name?: string | null;
  status: string;
  mode: string;
  occurred_at: string;
  queued_at: string;
  reason: string;
  suggested_entry?: number | null;
  suggested_stop_loss?: number | null;
  suggested_take_profit?: number | null;
  estimated_risk_reward?: number | null;
}

export interface BrokerAccount {
  id: string;
  name: string;
  broker_type: string;
  mode: string;
  enabled: boolean;
  live_trading_enabled: boolean;
  status: string;
  base_url?: string | null;
  settings_json: Record<string, unknown>;
  has_secret: boolean;
  supports_execution?: boolean;
  supports_sync?: boolean;
  capability_message?: string | null;
  last_sync_status?: string | null;
  last_sync_started_at?: string | null;
  last_sync_completed_at?: string | null;
  last_sync_message?: string | null;
}

export interface BrokerValidationResult {
  broker_type: string;
  supports_execution: boolean;
  supports_sync: boolean;
  message: string;
}

export interface BrokerAdapterStatus {
  broker_type: string;
  supports_execution: boolean;
  supports_sync: boolean;
  message: string;
}

export interface BrokerSyncResult {
  broker_account_id: string;
  broker_type: string;
  status: string;
  message: string;
  account_message: string;
  positions_message: string;
  orders_message: string;
  supports_execution: boolean;
  supports_sync: boolean;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface TaskMapping {
  id?: string;
  task_name: string;
  provider_type: string;
  model_name: string;
  fallback_chain: { provider_type: string; model_name: string; timeout_seconds?: number }[];
  timeout_seconds: number;
}

export interface SettingsOverview {
  providers: ProviderConfig[];
  task_mappings: TaskMapping[];
  risk_rules: RiskRule[];
  live_automation: TradingAutomationProfile;
  simulation_automation: TradingAutomationProfile;
  live_trading_enabled: boolean;
}

export interface Alert {
  id: string;
  category: string;
  severity: string;
  title: string;
  message: string;
  status: string;
  mode?: string | null;
  source_ref?: string | null;
  created_at: string;
}

export interface McpTool {
  name: string;
  description?: string | null;
}

export interface McpResource {
  uri: string;
  name?: string | null;
  description?: string | null;
}

export interface McpStatus {
  enabled: boolean;
  reachable: boolean;
  server_url: string;
  transport: string;
  message: string;
  server_name?: string | null;
  tools: McpTool[];
  resources: McpResource[];
}

export interface HealthReadyStatus {
  status: string;
  details: Record<string, string>;
}
