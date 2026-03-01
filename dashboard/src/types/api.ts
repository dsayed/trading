export interface Config {
  stake: number;
  max_position_pct: number;
  stop_loss_pct: number;
  data_provider: string;
  strategies: string[];
  risk_manager: string;
  broker: string;
}

export interface ConfigUpdate {
  stake?: number;
  max_position_pct?: number;
  stop_loss_pct?: number;
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
