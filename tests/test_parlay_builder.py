"""Parlay candidate builder tests including correlation filtering."""

from __future__ import annotations

import pandas as pd
import pytest

from betting_system.optimizer.parlay_builder import _corr_lookup, build_parlay_candidates


def _leg(player_id: str, game_id: str, p_hit: float = 0.62):
    return {
        "game_id": game_id,
        "market_type": "player_points_over",
        "player_id": player_id,
        "line": 20.5,
        "odds_american": -110,
        "p_hit": p_hit,
        "edge": 0.05,
        "ev_per_unit": 0.07,
    }


def test_build_parlay_candidates_returns_ranked_ev():
    """Two-leg portfolios are ranked by positive EV."""
    legs = [_leg("p1", "g1"), _leg("p2", "g2", p_hit=0.64)]
    candidates = build_parlay_candidates(legs)
    assert candidates
    assert candidates[0]["ev_per_unit"] >= candidates[-1]["ev_per_unit"]


def test_corr_lookup_symmetric(tmp_path):
    """Correlation matrix lookup works in both directions."""
    corr_df = pd.DataFrame(
        {
            "market_type_a": ["player_points_over"],
            "player_id_a": ["p1"],
            "market_type_b": ["player_assists_over"],
            "player_id_b": ["p2"],
            "corr": [0.25],
        }
    )
    a = {"market_type": "player_assists_over", "player_id": "p2"}
    b = {"market_type": "player_points_over", "player_id": "p1"}
    val = _corr_lookup(corr_df, a, b, default=0.0)
    assert val == pytest.approx(0.25)
