"""World Cup 2026 adapter tests."""

from __future__ import annotations

from betting_system.worldcup.score_model import (
    build_wc_features,
    derived_market_probs,
    forecast_match,
    ingest_wc_matches,
    poisson_score_matrix,
)


def test_poisson_score_matrix_sums_to_one():
    """Score probability matrix is normalized."""
    mat = poisson_score_matrix(1.4, 1.1)
    assert abs(mat.sum() - 1.0) < 1e-6


def test_derived_market_probs():
    """1X2 and totals derived from score matrix."""
    mat = poisson_score_matrix(1.5, 1.0)
    probs = derived_market_probs(mat)
    assert abs(probs["home_win"] + probs["draw"] + probs["away_win"] - 1.0) < 1e-6
    assert 0 <= probs["over_2_5"] <= 1


def test_forecast_match_returns_xg():
    """forecast_match includes xG inputs."""
    out = forecast_match(1.6, 0.9)
    assert "home_xg" in out
    assert out["home_xg"] == 1.6


def test_ingest_wc_matches_fixture():
    """WC fixture loader returns match rows."""
    df = ingest_wc_matches()
    assert len(df) >= 2
    assert "home_goals" in df.columns


def test_build_wc_features_team_form():
    """Team rolling goals features include shifted rolling columns."""
    matches = ingest_wc_matches()
    feats = build_wc_features(matches)
    assert not feats.empty
    assert "gf_roll_5" in feats.columns
    assert "ga_roll_5" in feats.columns
