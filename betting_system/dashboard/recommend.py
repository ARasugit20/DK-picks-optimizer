"""Target-multiplier parlay recommendations for the dashboard."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any

from betting_system.config import load_settings
from betting_system.optimizer.parlay_builder import build_parlay_candidates
from betting_system.optimizer.staking import parlay_stake_cap


@dataclass(frozen=True)
class ParlayRecommendation:
    """One ranked portfolio aimed at a payout multiplier."""

    leg_count: int
    target_multiplier: float
    stake: float
    payout_if_win: float
    implied_multiplier: float
    p_parlay: float
    ev_per_unit: float
    legs: list[dict[str, Any]]
    parlay_id: str
    match_quality: str


def _pool_legs(legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Trim and sort the leg pool for combinatorial search."""
    settings = load_settings()
    dash = settings.dashboard
    max_pool = int(dash.get("max_pool_legs", 22))
    pool = [leg for leg in legs if leg.get("worthy", True)]
    pool.sort(key=lambda x: float(x.get("p_hit", 0)), reverse=True)
    return pool[:max_pool]


def _score_candidate(candidate: dict[str, Any], target_mult: float) -> float:
    """Higher is better: balance hit probability vs closeness to target payout."""
    dec = float(candidate["decimal_odds"])
    p = float(candidate["p_parlay"])
    if dec <= 1.0:
        return -1.0
    log_err = abs(math.log(dec) - math.log(target_mult))
    closeness = 1.0 / (1.0 + log_err)
    return p * closeness + 0.15 * float(candidate.get("ev_per_unit", 0))


def find_best_parlay(
    legs: list[dict[str, Any]],
    *,
    leg_count: int,
    target_multiplier: float,
    bankroll: float,
) -> ParlayRecommendation | None:
    """Pick the best *leg_count*-leg portfolio near *target_multiplier* for *bankroll*."""
    settings = load_settings()
    dash = settings.dashboard
    tol = float(dash.get("multiplier_tolerance_pct", 0.30))
    pool = _pool_legs(legs)
    if len(pool) < leg_count:
        return None

    candidates = build_parlay_candidates(
        pool,
        min_legs=leg_count,
        max_legs=leg_count,
    )
    if not candidates:
        return None

    lo = target_multiplier * (1.0 - tol)
    hi = target_multiplier * (1.0 + tol)
    in_band = [c for c in candidates if lo <= float(c["decimal_odds"]) <= hi]
    shortlist = in_band if in_band else candidates[: min(50, len(candidates))]
    best = max(shortlist, key=lambda c: _score_candidate(c, target_multiplier))
    dec = float(best["decimal_odds"])
    stake_cap = parlay_stake_cap(bankroll=bankroll)
    stake = min(bankroll, stake_cap)
    payout = stake * dec
    quality = "on_target" if in_band else "closest_available"

    return ParlayRecommendation(
        leg_count=leg_count,
        target_multiplier=target_multiplier,
        stake=round(stake, 2),
        payout_if_win=round(payout, 2),
        implied_multiplier=round(dec, 2),
        p_parlay=round(float(best["p_parlay"]), 4),
        ev_per_unit=round(float(best["ev_per_unit"]), 4),
        legs=list(best["legs"]),
        parlay_id=str(uuid.uuid4()),
        match_quality=quality,
    )


def recommend_all_targets(
    legs: list[dict[str, Any]],
    *,
    bankroll: float,
    leg_counts: list[int] | None = None,
    multipliers: list[int] | None = None,
) -> list[ParlayRecommendation]:
    """Build recommendations for each leg-count × multiplier pair."""
    settings = load_settings()
    dash = settings.dashboard
    leg_counts = leg_counts or list(dash.get("leg_count_options", [5, 10, 15]))
    multipliers = multipliers or list(dash.get("multiplier_targets", [10, 15]))
    out: list[ParlayRecommendation] = []
    for n in leg_counts:
        for mult in multipliers:
            rec = find_best_parlay(
                legs,
                leg_count=int(n),
                target_multiplier=float(mult),
                bankroll=bankroll,
            )
            if rec is not None:
                out.append(rec)
    return out
