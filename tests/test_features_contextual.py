"""Contextual feature column tests."""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
import pytest

from betting_system.pipeline.features import build_features


@pytest.fixture
def contextual_inputs(tmp_path):
    """Stat + odds frames with home_away for contextual features."""
    stat = pd.DataFrame(
        {
            "game_id": ["g1", "g2", "g3"],
            "player_id": ["p1", "p1", "p1"],
            "stat_type": ["points", "points", "points"],
            "actual_value": [22.0, 28.0, 19.0],
            "hit": [True, False, True],
            "game_date": [date(2024, 1, 1), date(2024, 1, 3), date(2024, 1, 4)],
            "home_away": ["home", "away", "home"],
        }
    )
    odds = pd.DataFrame(
        {
            "game_id": ["g1", "g2", "g3"],
            "player_id": ["p1", "p1", "p1"],
            "market_type": ["player_points_over"] * 3,
            "line": [20.5, 25.5, 18.5],
            "odds_american": [-110, -115, -108],
            "implied_prob": [0.52, 0.53, 0.51],
            "ingested_at": pd.to_datetime(
                ["2024-01-01T10:00:00Z", "2024-01-03T10:00:00Z", "2024-01-04T10:00:00Z"]
            ),
        }
    )
    stat_path = tmp_path / "stat.parquet"
    odds_path = tmp_path / "odds.parquet"
    stat.to_parquet(stat_path, index=False)
    odds.to_parquet(odds_path, index=False)
    return stat_path, odds_path


def test_contextual_features_not_null(contextual_inputs, test_config_path, tmp_path):
    """home_away and days_rest must be populated after build_features."""
    os.environ["BETTING_CONFIG_PATH"] = str(test_config_path)
    stat_path, odds_path = contextual_inputs
    out = build_features(
        stat_results_path=stat_path,
        odds_parquet_path=odds_path,
        out_path=tmp_path / "features.parquet",
    )
    df = pd.read_parquet(out)
    assert df["home_away"].notna().all()
    assert df["days_rest"].notna().all()
    assert "back_to_back" in df.columns
