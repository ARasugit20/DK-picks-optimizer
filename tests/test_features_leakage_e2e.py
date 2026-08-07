"""End-to-end temporal leakage guards for build_features artifacts."""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
import pytest

from betting_system.pipeline.features import build_features


@pytest.fixture
def leakage_inputs(tmp_path):
    """Multi-row stat + odds frames for adversarial leakage checks."""
    stat = pd.DataFrame(
        {
            "game_id": ["g1", "g2", "g3", "g4"],
            "player_id": ["p1", "p1", "p1", "p1"],
            "player_name": ["Test Player"] * 4,
            "team_abbr": ["TST"] * 4,
            "opponent_team_abbr": ["OPP"] * 4,
            "stat_type": ["points"] * 4,
            "actual_value": [22.0, 28.0, 19.0, 31.0],
            "hit": [True, False, True, True],
            "game_date": [date(2024, 1, 1), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 6)],
            "home_away": ["home", "away", "home", "away"],
            "minutes": [32.0, 35.0, 28.0, 36.0],
        }
    )
    odds = pd.DataFrame(
        {
            "game_id": ["g1", "g2", "g3", "g4"],
            "player_id": ["p1", "p1", "p1", "p1"],
            "market_type": ["player_points_over"] * 4,
            "line": [20.5, 25.5, 18.5, 24.5],
            "odds_american": [-110, -115, -108, -112],
            "implied_prob": [0.52, 0.53, 0.51, 0.52],
            "ingested_at": pd.to_datetime(
                [
                    "2024-01-01T10:00:00Z",
                    "2024-01-03T10:00:00Z",
                    "2024-01-04T10:00:00Z",
                    "2024-01-06T10:00:00Z",
                ]
            ),
        }
    )
    stat_path = tmp_path / "stat.parquet"
    odds_path = tmp_path / "odds.parquet"
    stat.to_parquet(stat_path, index=False)
    odds.to_parquet(odds_path, index=False)
    return stat_path, odds_path, stat.copy()


def test_build_features_unchanged_when_future_rows_perturbed(
    leakage_inputs,
    test_config_path,
    tmp_path,
):
    """Perturbing future stat values must not change earlier feature rows."""
    os.environ["BETTING_CONFIG_PATH"] = str(test_config_path)
    stat_path, odds_path, stat_df = leakage_inputs

    baseline_out = build_features(
        stat_results_path=stat_path,
        odds_parquet_path=odds_path,
        out_path=tmp_path / "baseline.parquet",
    )
    baseline = pd.read_parquet(baseline_out).sort_values(["game_date", "game_id"]).reset_index(drop=True)

    stat_df.loc[stat_df["game_id"] == "g4", "actual_value"] = 999.0
    stat_df.loc[stat_df["game_id"] == "g4", "hit"] = False
    stat_df.to_parquet(stat_path, index=False)

    perturbed_out = build_features(
        stat_results_path=stat_path,
        odds_parquet_path=odds_path,
        out_path=tmp_path / "perturbed.parquet",
    )
    perturbed = pd.read_parquet(perturbed_out).sort_values(["game_date", "game_id"]).reset_index(drop=True)

    compare_cols = [
        c
        for c in baseline.columns
        if c not in {"actual_value", "hit"}
    ]
    pd.testing.assert_frame_equal(
        baseline.loc[baseline["game_id"] != "g4", compare_cols],
        perturbed.loc[perturbed["game_id"] != "g4", compare_cols],
        check_dtype=False,
    )
