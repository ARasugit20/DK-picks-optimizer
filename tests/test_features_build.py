"""Integration tests for build_features parquet pipeline."""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
import pytest

from betting_system.pipeline.features import build_features


@pytest.fixture
def feature_inputs(tmp_path):
    """Minimal stat + odds frames for build_features."""
    stat = pd.DataFrame(
        {
            "game_id": ["g1", "g2"],
            "player_id": ["p1", "p1"],
            "stat_type": ["points", "points"],
            "actual_value": [22.0, 28.0],
            "hit": [True, False],
            "game_date": [date(2024, 1, 1), date(2024, 1, 3)],
        }
    )
    odds = pd.DataFrame(
        {
            "game_id": ["g1", "g2"],
            "player_id": ["p1", "p1"],
            "market_type": ["player_points_over", "player_points_over"],
            "line": [20.5, 25.5],
            "odds_american": [-110, -115],
            "implied_prob": [0.52, 0.53],
            "ingested_at": pd.to_datetime(["2024-01-01T10:00:00Z", "2024-01-03T10:00:00Z"]),
        }
    )
    stat_path = tmp_path / "stat.parquet"
    odds_path = tmp_path / "odds.parquet"
    stat.to_parquet(stat_path, index=False)
    odds.to_parquet(odds_path, index=False)
    return stat_path, odds_path


def test_build_features_writes_parquet(feature_inputs, test_config_path, tmp_path):
    """build_features joins odds and stats and writes leakage-free features."""
    os.environ["BETTING_CONFIG_PATH"] = str(test_config_path)
    stat_path, odds_path = feature_inputs
    out = build_features(
        stat_results_path=stat_path,
        odds_parquet_path=odds_path,
        out_path=tmp_path / "features.parquet",
    )
    assert out.exists()
    df = pd.read_parquet(out)
    assert "actual_value_roll_mean_3" in df.columns
    assert "hit" in df.columns
    assert len(df) == 2
