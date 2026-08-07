from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DataSource = Literal["live", "fixture_fallback"]


class OddsRecord(BaseModel):
    game_id: str
    market_type: str
    player_id: str
    line: float
    odds_american: int
    implied_prob: float
    bookmaker: str
    ingested_at: datetime
    is_closing: bool = False

    @field_validator("implied_prob")
    @classmethod
    def _prob_in_range(cls, v: float) -> float:
        if not (0.0 < v < 1.0):
            raise ValueError("implied_prob must be in (0,1)")
        return v


class StatResult(BaseModel):
    game_id: str
    player_id: str
    stat_type: str
    actual_value: float
    hit: bool


class EdgeResult(BaseModel):
    p_hit: float = Field(..., ge=0.0, le=1.0)
    p_market: float = Field(..., ge=0.0, le=1.0)
    edge: float
    ev_per_unit: float
    worthy: bool


class PickLeg(BaseModel):
    game_id: str
    market_type: str
    player_id: str
    line: float
    odds_american: int
    p_hit: float
    edge: float
    ev_per_unit: float


class ParlayPick(BaseModel):
    parlay_id: str
    legs: list[PickLeg]
    p_parlay: float
    ev_per_unit: float
    stake: float
    expected_payout: float


class SlatePicks(BaseModel):
    slate_id: str
    generated_at: datetime
    bankroll: float
    total_exposure: float
    parlays: list[ParlayPick]
    data_source: DataSource | None = None


class MarketOpportunitiesMeta(BaseModel):
    """Metadata block for market opportunity artifacts."""

    model_config = ConfigDict(extra="allow")

    data_source: DataSource | None = None
    is_live: bool
    sources: list[str] = Field(default_factory=list)
    fetched_at: str | None = None
    fallback_reason: str | None = None


class MarketOpportunity(BaseModel):
    """Single scored prediction-market opportunity."""

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    market_id: str
    question: str
    market_price: float = Field(ge=0.0, le=1.0)
    model_prob: float = Field(ge=0.0, le=1.0)
    edge: float
    data_source: DataSource
    event_id: str | None = None
    outcome: str | None = None
    venue: str | None = None
    category: str | None = None
    fair_price: float | None = None
    ev_per_unit: float | None = None
    edge_pct: float | None = None
    payout_multiplier: float | None = None
    confidence_pct: float | None = None
    rationale: str | None = None


class EdgeSummaryResponse(BaseModel):
    """Resolved Edge Desk evaluation metrics."""

    logged_edges: int
    resolved_edges: int
    mean_edge: float | None = None
    mean_edge_realized: float | None = None
    brier: float | None = None
    ece: float | None = None
    t_stat_edge_vs_zero: float | None = None
    p_value_edge_vs_zero_approx: float | None = None
    status: str


class PortfolioPosition(BaseModel):
    """Open prediction-market position."""

    model_config = ConfigDict(extra="allow")

    market_id: str
    question: str
    side: str
    qty: float
    avg_price: float
    mark_price: float
    pnl: float
    venue: str


class AccountSummary(BaseModel):
    """Account-level summary for Edge Desk."""

    equity: float
    daily_edge_captured: float
    open_pnl: float


class MarketOpportunitiesResponse(BaseModel):
    """Top-level market opportunities artifact served by the API."""

    meta: MarketOpportunitiesMeta
    data_source: DataSource
    hero_pick: MarketOpportunity | None
    opportunities: list[MarketOpportunity]
    edge_summary: EdgeSummaryResponse
    portfolio: list[PortfolioPosition]
    account: AccountSummary


class MarketPortfolioResponse(BaseModel):
    """Portfolio slice extracted from market opportunities."""

    data_source: DataSource
    portfolio: list[PortfolioPosition]
    account: AccountSummary


class HealthResponse(BaseModel):
    """Service health and artifact availability."""

    status: str
    service: str
    processed_path: str
    picks_today_exists: bool
    market_opportunities_exists: bool
    config_valid: bool


class ModelStatusResponse(BaseModel):
    """Model artifact registry status."""

    model_config = ConfigDict(protected_namespaces=())

    model_available: bool
    model_path: str
    metrics_available: bool
    metrics_path: str | None = None
    metrics: dict[str, Any] | None = None


class BankrollResponse(BaseModel):
    """Capital allocation snapshot."""

    bankroll: float
    exposure: float = 0.0
    pnl: float = 0.0


class ResultPostResponse(BaseModel):
    """Acknowledgement for submitted settlement results."""

    ok: bool


class MoneyWeightedAttribution(BaseModel):
    """Money-weighted trade attribution block."""

    resolved_trades: int
    total_notional: float
    total_pnl: float
    roi: float | None = None
    money_weighted_brier: float | None = None
    money_weighted_edge: float | None = None


class PnlAttributionResponse(BaseModel):
    """PnL attribution for market trades."""

    trade_count: int
    money_weighted: MoneyWeightedAttribution


class CalibrationMetricsResponse(BaseModel):
    """Calibration artifact payload (flexible keys from training pipeline)."""

    model_config = ConfigDict(extra="allow")

    data_source: DataSource | None = None

