"""Optimizer hardening tests tied to config thresholds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from betting_system.config import load_settings
from betting_system.optimizer.parlay_builder import build_parlay_candidates
from betting_system.optimizer.portfolio import optimize_slate
from betting_system.optimizer.staking import fractional_kelly_stake, parlay_stake_cap


def _corr_csv(tmp_path: Path, legs: list[dict[str, Any]], corr: float) -> Path:
    path = tmp_path / "corr.csv"
    pd.DataFrame(
        [
            {
                "market_type_a": legs[0]["market_type"],
                "player_id_a": legs[0]["player_id"],
                "market_type_b": legs[1]["market_type"],
                "player_id_b": legs[1]["player_id"],
                "corr": corr,
            }
        ]
    ).to_csv(path, index=False)
    return path


def test_correlation_discount_reduces_combined_probability(tmp_path: Path, synthetic_worthy_legs):
    """A configured pair correlation lowers the same parlay vs uncorrelated legs."""
    cfg = load_settings().model
    corr = float(cfg["correlation_max_pair"]) / 2
    corr_path = _corr_csv(tmp_path, synthetic_worthy_legs, corr)

    base = build_parlay_candidates(synthetic_worthy_legs[:2], min_legs=2, max_legs=2)[0]
    discounted = build_parlay_candidates(
        synthetic_worthy_legs[:2],
        corr_path=corr_path,
        min_legs=2,
        max_legs=2,
    )[0]

    assert discounted["corr_discount"] == 1.0 - corr
    assert discounted["p_parlay"] < base["p_parlay"]
    assert discounted["ev_per_unit"] < base["ev_per_unit"]


def test_portfolio_respects_max_parlays_per_slate(synthetic_worthy_legs):
    """Optimizer does not return more parlays than configured."""
    cfg = load_settings().model
    slate = optimize_slate(
        slate_id="optimizer-smoke",
        worthy_legs=synthetic_worthy_legs,
        bankroll=1_000.0,
    )
    assert len(slate.parlays) <= int(cfg["max_parlays_per_slate"])


def test_fractional_kelly_respects_max_stake_pct(synthetic_worthy_legs):
    """Single-leg Kelly stake is capped by configured max_stake_pct."""
    cfg = load_settings().model
    bankroll = 1_000.0
    decision = fractional_kelly_stake(
        bankroll=bankroll,
        p_hit=float(synthetic_worthy_legs[0]["p_hit"]),
        odds_american=int(synthetic_worthy_legs[0]["odds_american"]),
    )
    assert decision.stake <= bankroll * float(cfg["max_stake_pct"])


def test_total_slate_exposure_respects_configured_cap(synthetic_worthy_legs):
    """Total optimized exposure stays within max_slate_exposure."""
    cfg = load_settings().model
    bankroll = 1_000.0
    slate = optimize_slate(
        slate_id="exposure-smoke",
        worthy_legs=synthetic_worthy_legs,
        bankroll=bankroll,
    )
    assert slate.total_exposure <= bankroll * float(cfg["max_slate_exposure"])
    for parlay in slate.parlays:
        assert parlay.stake <= parlay_stake_cap(bankroll=bankroll)
