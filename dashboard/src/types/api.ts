export interface Config {
  stake: number;
  max_position_pct: number;
  stop_loss_pct: number;
  data_provider: string;
  strategies: string[];
  risk_manager: string;
  broker: string;
  polygon_api_key_set: boolean;
  polygon_api_key_hint: string;
  options_provider: string | null;
  discovery_provider: string | null;
  forex_provider: string | null;
  fmp_api_key_set: boolean;
  fmp_api_key_hint: string;
  marketdata_api_key_set: boolean;
  marketdata_api_key_hint: string;
  twelvedata_api_key_set: boolean;
  twelvedata_api_key_hint: string;
}

export interface ConfigUpdate {
  stake?: number;
  max_position_pct?: number;
  stop_loss_pct?: number;
  data_provider?: string;
  polygon_api_key?: string;
  options_provider?: string | null;
  discovery_provider?: string | null;
  forex_provider?: string | null;
  fmp_api_key?: string;
  marketdata_api_key?: string;
  twelvedata_api_key?: string;
}

export interface Watchlist {
  id: number;
  name: string;
  symbols: string[];
  created_at: string;
  updated_at: string;
}

export interface WatchlistCreate {
  name: string;
  symbols: string[];
}

export interface WatchlistUpdate {
  name?: string;
  symbols?: string[];
}

export interface Signal {
  symbol: string;
  company_name: string | null;
  direction: string;
  conviction: number;
  rationale: string;
  strategy_name: string;
  quantity: number;
  order_type: string;
  limit_price: number | null;
  stop_price: number | null;
  order_rationale: string;
  playbook: string;
  position_value: number | null;
  risk_amount: number | null;
  reward_amount: number | null;
}

export interface ScanRequest {
  watchlist_id?: number;
  symbols?: string[];
  lookback_days?: number;
}

export interface ScanResponse {
  id: number;
  ran_at: string;
  signal_count: number;
  signals: Signal[];
}

export interface ScanSummary {
  id: number;
  ran_at: string;
  watchlist_name: string | null;
  symbols: string[];
  signal_count: number;
}

// Positions
export interface TaxLot {
  quantity: number;
  cost_basis: number;
  purchase_date: string;
  is_long_term: boolean;
  days_to_long_term: number;
}

export interface Position {
  id: number;
  symbol: string;
  asset_class: string;
  exchange: string | null;
  total_quantity: number;
  average_cost: number;
  tax_lots: TaxLot[];
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PositionCreate {
  symbol: string;
  quantity: number;
  cost_basis: number;
  purchase_date: string;
  asset_class?: string;
  exchange?: string;
  notes?: string;
}

export interface AddTaxLot {
  quantity: number;
  cost_basis: number;
  purchase_date: string;
}

// Advise
export interface OptionContractInfo {
  contract_symbol: string;
  strike: number;
  expiration: string;
  option_type: string;
  bid: number;
  ask: number;
  mid_price: number;
  volume: number;
  open_interest: number;
  implied_volatility: number;
}

export interface Play {
  play_type: string;
  title: string;
  rationale: string;
  conviction: number;
  option_contract: OptionContractInfo | null;
  contracts: number;
  premium: number;
  max_profit: number | null;
  max_loss: number | null;
  breakeven: number | null;
  tax_note: string | null;
  playbook: string;
  advisor_name: string;
}

export interface PositionAdvice {
  symbol: string;
  current_price: number;
  unrealized_pnl: number;
  total_quantity: number;
  average_cost: number;
  plays: Play[];
}

export interface AdviseRequest {
  position_ids?: number[];
  advisor_names?: string[];
  lookback_days?: number;
}

export interface AdviseResponse {
  positions: PositionAdvice[];
}

// Scanner
export interface ScannerRequest {
  universe?: string;
  symbols?: string[];
  strategies?: string[];
  max_results?: number;
  lookback_days?: number;
  holding_period?: string;
}

export interface UniverseResponse {
  predefined: string[];
  dynamic: string[];
}

export interface ScannerResponse {
  id: number;
  ran_at: string;
  signal_count: number;
  universe: string | null;
  signals: Signal[];
}

// Diagnostics
export interface ProviderStatus {
  name: string;
  role: string;
  ok: boolean;
  latency_ms: number;
  bars_returned: number;
  error: string | null;
}

export interface DiagnosticsResponse {
  providers: ProviderStatus[];
}

// Import
export interface ImportedPosition {
  symbol: string;
  quantity: number;
  cost_basis: number;
  purchase_date: string;
  asset_class: string;
  account: string | null;
  description: string | null;
  status: 'new' | 'duplicate' | 'warning';
  warnings: string[];
}

export interface ImportSummary {
  total: number;
  new: number;
  duplicates: number;
  warnings: number;
}

export interface ImportPreviewResponse {
  broker_detected: string;
  positions: ImportedPosition[];
  summary: ImportSummary;
}

export interface ImportCommitRequest {
  positions: ImportedPosition[];
}

export interface ImportCommitResponse {
  imported: number;
  positions: Position[];
}
