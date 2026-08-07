from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


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
    legs: List[PickLeg]
    p_parlay: float
    ev_per_unit: float
    stake: float
    expected_payout: float


class SlatePicks(BaseModel):
    slate_id: str
    generated_at: datetime
    bankroll: float
    total_exposure: float
    parlays: List[ParlayPick]


# -- Market / Edge schemas for API validation ---------------------------------


class MarketOpportunity(BaseModel):
    market_id: Optional[str]
    event_id: Optional[str]
    outcome: Optional[str]
    market_price: Optional[float]
    fair_price: Optional[float]
    model_prob: Optional[float]
    edge: Optional[float]
    ev_per_unit: Optional[float]
    venue: Optional[str]
    category: Optional[str]
    question: Optional[str]
    volume: Optional[float]
    open_interest: Optional[float]
    price_history_market: Optional[List[float]] = None
    price_history_model: Optional[List[float]] = None
    data_source: Optional[str] = None
    fetched_at: Optional[datetime] = None
    is_live: Optional[bool] = None
    confidence_pct: Optional[float] = None
    rationale: Optional[str] = None


class EdgeSummarySchema(BaseModel):
    logged_edges: int
    resolved_edges: int
    mean_edge: Optional[float]
    mean_edge_realized: Optional[float]
    brier: Optional[float]
    ece: Optional[float]
    t_stat_edge_vs_zero: Optional[float]
    p_value_edge_vs_zero_approx: Optional[float]
    status: str


class MoneyWeightedSummarySchema(BaseModel):
    resolved_trades: int
    total_notional: float
    total_pnl: float
    roi: Optional[float]
    money_weighted_brier: Optional[float]
    money_weighted_edge: Optional[float]


class MarketPnlAttribution(BaseModel):
    trade_count: int
    money_weighted: Optional[MoneyWeightedSummarySchema]


class MarketPortfolioResponse(BaseModel):
    data_source: str
    portfolio: List[Any]
    account: dict[str, Any]


class MarketOpportunities(BaseModel):
    meta: Optional[dict[str, Any]] = None
    data_source: str
    hero_pick: Optional[MarketOpportunity] = None
    opportunities: List[MarketOpportunity]
    edge_summary: Optional[EdgeSummarySchema] = None
    portfolio: Optional[List[Any]] = None
    account: Optional[dict[str, Any]] = None


class OkResponse(BaseModel):
    ok: bool
