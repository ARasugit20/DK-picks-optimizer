"""Target-multiplier portfolio recommendations for the dashboard."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from betting_system.config import load_settings
from betting_system.optimizer.parlay_builder import build_parlay_candidates
from betting_system.optimizer.staking import parlay_stake_cap


ObjectiveMode = Literal["conservative", "balanced", "aggressive", "max_ev", "max_prob", "target_multiplier"]


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
    objective_mode: str = "balanced"
    selection_reasons: list[str] = field(default_factory=list)


def _objective_weights(mode: ObjectiveMode) -> dict[str, float]:
    """Return scoring weights for a recommendation objective mode."""
    settings = load_settings()
    rec_cfg = settings.raw.get("recommendations", {})
    defaults = {
        "conservative": {"prob_weight": 0.7, "ev_weight": 0.2, "correlation_penalty_weight": 0.1, "target_multiplier_weight": 0.0},
        "balanced": {"prob_weight": 0.4, "ev_weight": 0.35, "correlation_penalty_weight": 0.15, "target_multiplier_weight": 0.1},
        "aggressive": {"prob_weight": 0.15, "ev_weight": 0.55, "correlation_penalty_weight": 0.1, "target_multiplier_weight": 0.2},
        "max_ev": {"prob_weight": 0.1, "ev_weight": 0.8, "correlation_penalty_weight": 0.1, "target_multiplier_weight": 0.0},
        "max_prob": {"prob_weight": 0.85, "ev_weight": 0.1, "correlation_penalty_weight": 0.05, "target_multiplier_weight": 0.0},
        "target_multiplier": {"prob_weight": 0.35, "ev_weight": 0.15, "correlation_penalty_weight": 0.1, "target_multiplier_weight": 0.4},
    }
    base = defaults.get(mode, defaults["balanced"])
    return {k: float(rec_cfg.get(k, base[k])) for k in base}


def _pool_legs(legs: list[dict[str, Any]], *, mode: ObjectiveMode) -> list[dict[str, Any]]:
    """Trim and sort the leg pool for combinatorial search."""
    settings = load_settings()
    dash = settings.dashboard
    max_pool = int(dash.get("max_pool_legs", 22))
    pool = [leg for leg in legs if leg.get("worthy", True)]
    if mode in ("max_ev", "aggressive"):
        pool.sort(key=lambda x: float(x.get("ev_per_unit", 0)), reverse=True)
    elif mode in ("max_prob", "conservative"):
        pool.sort(key=lambda x: float(x.get("p_hit", 0)), reverse=True)
    else:
        pool.sort(key=lambda x: float(x.get("p_hit", 0)) * 0.6 + float(x.get("ev_per_unit", 0)) * 0.4, reverse=True)
    return pool[:max_pool]


def _score_candidate(
    candidate: dict[str, Any],
    target_mult: float,
    *,
    mode: ObjectiveMode,
) -> float:
    """Score a portfolio candidate under the chosen objective mode."""
    weights = _objective_weights(mode)
    dec = float(candidate["decimal_odds"])
    p = float(candidate["p_parlay"])
    ev = float(candidate.get("ev_per_unit", 0))
    if dec <= 1.0:
        return -1.0
    log_err = abs(math.log(dec) - math.log(max(target_mult, 1.01)))
    mult_closeness = 1.0 / (1.0 + log_err)
    corr_penalty = 1.0 - float(candidate.get("corr_discount", 1.0))
    return (
        weights["prob_weight"] * p
        + weights["ev_weight"] * max(ev, 0)
        + weights["target_multiplier_weight"] * mult_closeness
        - weights["correlation_penalty_weight"] * corr_penalty
    )


def _selection_reasons(candidate: dict[str, Any], mode: ObjectiveMode) -> list[str]:
    """Human-readable reasons for why a portfolio was selected."""
    reasons = []
    p = float(candidate["p_parlay"])
    ev = float(candidate.get("ev_per_unit", 0))
    if mode in ("max_prob", "conservative"):
        reasons.append(f"High joint probability ({p:.1%})")
    if mode in ("max_ev", "aggressive"):
        reasons.append(f"Strong EV per unit ({ev:+.3f})")
    if mode == "target_multiplier":
        reasons.append(f"Near target payout ({float(candidate['decimal_odds']):.2f}x implied)")
    if float(candidate.get("corr_discount", 1.0)) < 0.95:
        reasons.append("Correlation-adjusted portfolio")
    if not reasons:
        reasons.append("Balanced probability and EV")
    return reasons


def find_best_parlay(
    legs: list[dict[str, Any]],
    *,
    leg_count: int,
    target_multiplier: float,
    bankroll: float,
    objective_mode: ObjectiveMode = "balanced",
) -> ParlayRecommendation | None:
    """Pick the best leg_count portfolio for bankroll under objective_mode."""
    settings = load_settings()
    dash = settings.dashboard
    tol = float(dash.get("multiplier_tolerance_pct", 0.30))
    pool = _pool_legs(legs, mode=objective_mode)
    if len(pool) < leg_count:
        return None

    candidates = build_parlay_candidates(pool, min_legs=leg_count, max_legs=leg_count)
    if not candidates:
        return None

    if objective_mode == "target_multiplier":
        lo = target_multiplier * (1.0 - tol)
        hi = target_multiplier * (1.0 + tol)
        in_band = [c for c in candidates if lo <= float(c["decimal_odds"]) <= hi]
        shortlist = in_band if in_band else candidates[: min(50, len(candidates))]
    else:
        shortlist = candidates[: min(100, len(candidates))]

    best = max(shortlist, key=lambda c: _score_candidate(c, target_multiplier, mode=objective_mode))
    dec = float(best["decimal_odds"])
    stake_cap = parlay_stake_cap(bankroll=bankroll)
    stake = min(bankroll, stake_cap)
    payout = stake * dec
    in_band = objective_mode == "target_multiplier" and (
        target_multiplier * (1.0 - tol) <= dec <= target_multiplier * (1.0 + tol)
    )
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
        objective_mode=objective_mode,
        selection_reasons=_selection_reasons(best, objective_mode),
    )


def recommend_all_targets(
    legs: list[dict[str, Any]],
    *,
    bankroll: float,
    leg_counts: list[int] | None = None,
    multipliers: list[int] | None = None,
    objective_mode: ObjectiveMode = "balanced",
) -> list[ParlayRecommendation]:
    """Build recommendations for each leg-count x multiplier pair."""
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
                objective_mode=objective_mode,
            )
            if rec is not None:
                out.append(rec)
    return out
