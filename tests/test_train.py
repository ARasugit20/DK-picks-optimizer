"""Training helper and calibration metric tests."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from betting_system.pipeline.train import _select_features, _time_split, expected_calibration_error


def test_time_split_respects_holdout():
    """Train rows are strictly before holdout_start."""
    df = pd.DataFrame(
        {
            "game_date": [date(2024, 1, 1), date(2024, 1, 5), date(2024, 1, 10)],
            "hit": [1, 0, 1],
            "game_id": ["a", "b", "c"],
            "player_id": ["p"] * 3,
            "market_type": ["player_points_over"] * 3,
            "actual_value": [1.0, 2.0, 3.0],
            "line": [1.0, 2.0, 3.0],
        }
    )
    train, valid = _time_split(df, holdout_start=date(2024, 1, 5))
    assert len(train) == 1
    assert len(valid) == 2


def test_select_features_drops_leakage_columns():
    """Target and identifiers are excluded from the feature matrix."""
    df = pd.DataFrame(
        {
            "hit": [1, 0],
            "game_id": ["a", "b"],
            "player_id": ["p1", "p2"],
            "game_date": [date(2024, 1, 1), date(2024, 1, 2)],
            "market_type": ["player_points_over"] * 2,
            "actual_value": [10.0, 12.0],
            "line": [9.5, 11.5],
            "odds_american": [-110, -110],
        }
    )
    X, y = _select_features(df)
    assert "hit" not in X.columns
    assert "game_id" not in X.columns
    assert list(y) == [1, 0]


def test_expected_calibration_error_perfect_bins():
    """Perfect calibration yields ECE near zero."""
    y_true = np.array([0, 1, 0, 1])
    y_prob = np.array([0.1, 0.9, 0.2, 0.8])
    ece = expected_calibration_error(y_true, y_prob, n_bins=2)
    assert ece < 0.15
