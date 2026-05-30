"""Portfolio optimizer and Kelly staking constraint tests."""

from __future__ import annotations

import os

import pytest

from betting_system.config import load_settings
from betting_system.optimizer.staking import fractional_kelly_stake, parlay_stake_cap
from betting_system.optimizer.portfolio import optimize_slate
from betting_system.optimizer.parlay_builder import build_parlay_candidates, load_correlation_matrix


def _worthy_leg(**overrides):
    base = {
        "game_id": "g1",
        "market_type": "player_points_over",
        "player_id": "p1",
        "line": 24.5,
        "odds_american": -110,
        "p_hit": 0.62,
        "edge": 0.05,
        "ev_per_unit": 0.08,
    }
    base.update(overrides)
    return base


def test_kelly_stake_never_exceeds_max_stake_pct(test_config_path):
    """Kelly stake must respect max_stake_pct from config."""
    os.environ["BETTING_CONFIG_PATH"] = str(test_config_path)
    settings = load_settings(test_config_path)
    max_pct = float(settings.model["max_stake_pct"])
    bankroll = 10_000.0
    decision = fractional_kelly_stake(bankroll=bankroll, p_hit=0.99, odds_american=200)
    assert decision.stake <= bankroll * max_pct + 1e-9


def test_parlay_stake_cap_uses_config(test_config_path):
    """Parlay stake cap is bankroll * max_parlay_pct from config."""
    os.environ["BETTING_CONFIG_PATH"] = str(test_config_path)
    settings = load_settings(test_config_path)
    bankroll = 5000.0
    cap = parlay_stake_cap(bankroll=bankroll)
    assert cap == pytest.approx(bankroll * float(settings.model["max_parlay_pct"]))


def test_parlay_builder_rejects_same_player_twice():
    """Correlated multi-leg portfolios cannot duplicate the same player."""
    legs = [
        _worthy_leg(player_id="p1", game_id="g1"),
        _worthy_leg(player_id="p1", game_id="g2", market_type="player_assists_over"),
    ]
    candidates = build_parlay_candidates(legs)
    assert candidates == []


def test_optimize_slate_respects_max_parlays(test_config_path):
    """Slate optimizer stops at max_parlays_per_slate from config."""
    os.environ["BETTING_CONFIG_PATH"] = str(test_config_path)
    settings = load_settings(test_config_path)
    legs = [
        _worthy_leg(player_id=f"p{i}", game_id=f"g{i}", p_hit=0.65 + i * 0.01)
        for i in range(6)
    ]
    slate = optimize_slate(slate_id="test", worthy_legs=legs, bankroll=1000.0)
    assert len(slate.parlays) <= int(settings.model["max_parlays_per_slate"])


def test_load_correlation_matrix_missing_returns_empty(tmp_path):
    """Missing correlation file yields an empty matrix (no crash)."""
    df = load_correlation_matrix(tmp_path / "missing.parquet")
    assert df.empty
