from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from betting_system.config import load_settings
from betting_system.odds_math import american_to_decimal


@dataclass(frozen=True)
class StakeDecision:
    stake: float
    capped: bool


def fractional_kelly_stake(*, bankroll: float, p_hit: float, odds_american: int) -> StakeDecision:
    settings = load_settings()
    cfg = settings.model
    kelly_fraction = float(settings.model["kelly_fraction"])
    max_stake_pct = float(cfg["max_stake_pct"])

    dec = american_to_decimal(odds_american)
    b = dec - 1.0
    # Kelly for binary bet: f* = (bp - q) / b
    q = 1.0 - p_hit
    f_star = (b * p_hit - q) / b if b > 0 else 0.0
    f = max(0.0, f_star) * kelly_fraction
    stake = bankroll * f
    cap = bankroll * max_stake_pct
    if stake > cap:
        return StakeDecision(stake=cap, capped=True)
    return StakeDecision(stake=stake, capped=False)


def parlay_stake_cap(*, bankroll: float) -> float:
    settings = load_settings()
    return bankroll * float(settings.model["max_parlay_pct"])

