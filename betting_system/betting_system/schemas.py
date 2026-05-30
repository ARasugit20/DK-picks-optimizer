from __future__ import annotations

from datetime import datetime

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

