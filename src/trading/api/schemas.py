"""API request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
#  Config
# --------------------------------------------------------------------------- #


class ConfigResponse(BaseModel):
    stake: float
    max_position_pct: float
    stop_loss_pct: float
    data_provider: str
    strategies: list[str]
    risk_manager: str
    broker: str


class ConfigUpdateRequest(BaseModel):
    stake: float | None = None
    max_position_pct: float | None = None
    stop_loss_pct: float | None = None


# --------------------------------------------------------------------------- #
#  Watchlists
# --------------------------------------------------------------------------- #


class WatchlistResponse(BaseModel):
    id: int
    name: str
    symbols: list[str]
    created_at: str
    updated_at: str


class WatchlistCreateRequest(BaseModel):
    name: str
    symbols: list[str] = Field(default_factory=list)


class WatchlistUpdateRequest(BaseModel):
    name: str | None = None
    symbols: list[str] | None = None


# --------------------------------------------------------------------------- #
#  Scans
# --------------------------------------------------------------------------- #


class ScanRequest(BaseModel):
    watchlist_id: int | None = None
    symbols: list[str] | None = None
    lookback_days: int = 120


class SignalResponse(BaseModel):
    symbol: str
    direction: str
    conviction: float
    rationale: str
    strategy_name: str
    quantity: int
    order_type: str
    limit_price: float | None
    stop_price: float | None
    order_rationale: str
    playbook: str


class ScanResponse(BaseModel):
    id: int
    ran_at: str
    signal_count: int
    signals: list[SignalResponse]


class ScanSummaryResponse(BaseModel):
    id: int
    ran_at: str
    watchlist_name: str | None
    symbols: list[str]
    signal_count: int


# --------------------------------------------------------------------------- #
#  Positions
# --------------------------------------------------------------------------- #


class TaxLotResponse(BaseModel):
    quantity: int
    cost_basis: float
    purchase_date: str
    is_long_term: bool
    days_to_long_term: int


class PositionResponse(BaseModel):
    id: int
    symbol: str
    asset_class: str
    exchange: str | None
    total_quantity: int
    average_cost: float
    tax_lots: list[TaxLotResponse]
    notes: str | None
    created_at: str
    updated_at: str


class PositionCreateRequest(BaseModel):
    symbol: str
    quantity: int
    cost_basis: float
    purchase_date: str
    asset_class: str = "equity"
    exchange: str | None = None
    notes: str | None = None


class AddTaxLotRequest(BaseModel):
    quantity: int
    cost_basis: float
    purchase_date: str


class PositionUpdateRequest(BaseModel):
    notes: str | None = None


# --------------------------------------------------------------------------- #
#  Advise
# --------------------------------------------------------------------------- #


class OptionContractResponse(BaseModel):
    contract_symbol: str
    strike: float
    expiration: str
    option_type: str
    bid: float
    ask: float
    mid_price: float
    volume: int
    open_interest: int
    implied_volatility: float


class PlayResponse(BaseModel):
    play_type: str
    title: str
    rationale: str
    conviction: float
    option_contract: OptionContractResponse | None = None
    contracts: int
    premium: float
    max_profit: float | None = None
    max_loss: float | None = None
    breakeven: float | None = None
    tax_note: str | None = None
    playbook: str
    advisor_name: str


class PositionAdviceResponse(BaseModel):
    symbol: str
    current_price: float
    unrealized_pnl: float
    total_quantity: int
    average_cost: float
    plays: list[PlayResponse]


class AdviseRequest(BaseModel):
    position_ids: list[int] | None = None
    advisor_names: list[str] | None = None
    lookback_days: int = 120


class AdviseResponse(BaseModel):
    positions: list[PositionAdviceResponse]
