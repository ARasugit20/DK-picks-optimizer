"""Tests for leakage-free rolling feature construction."""

from __future__ import annotations

import pandas as pd
import pytest

from betting_system.pipeline.features import _rolling_features


def test_rolling_features_shift_prevents_leakage():
    """Future game values must not influence prior-row rolling means."""
    df = pd.DataFrame(
        {
            "player_id": ["a"] * 5,
            "stat_type": ["points"] * 5,
            "game_date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
            ).date,
            "actual_value": [10, 20, 30, 40, 50],
        }
    )
    out = _rolling_features(
        df,
        group_cols=["player_id", "stat_type"],
        value_col="actual_value",
        windows=[3],
        ewm_span=5,
    )
    assert pd.isna(out.loc[0, "actual_value_roll_mean_3"])
    assert out.loc[1, "actual_value_roll_mean_3"] == 10
    # Index 3: rolling window uses shifted prior values 10, 20, 30 only
    assert out.loc[3, "actual_value_roll_mean_3"] == pytest.approx(20.0)


def test_rolling_mean_excludes_current_row_value():
    """Row i rolling mean uses only games strictly before i."""
    df = pd.DataFrame(
        {
            "player_id": ["b"] * 3,
            "stat_type": ["assists"] * 3,
            "game_date": pd.to_datetime(["2024-02-01", "2024-02-02", "2024-02-03"]).date,
            "actual_value": [5, 15, 25],
        }
    )
    out = _rolling_features(
        df,
        group_cols=["player_id", "stat_type"],
        value_col="actual_value",
        windows=[2],
        ewm_span=5,
    )
    assert out.loc[2, "actual_value_roll_mean_2"] == pytest.approx(10.0)
