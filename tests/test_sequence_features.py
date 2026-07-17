"""Optional LSTM form feature tests (no torch required for helpers)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from betting_system.pipeline.sequence_features import (
    _build_sequences,
    apply_lstm_features_to_frame,
    train_lstm_form_features,
)


def test_build_sequences_shapes():
    """Sequences use prior games only and align with row indices."""
    df = pd.DataFrame(
        {
            "player_id": ["p1"] * 12,
            "stat_type": ["points"] * 12,
            "game_date": pd.date_range("2024-01-01", periods=12, freq="D"),
            "actual_value": np.arange(12, dtype=float),
        }
    )
    X, y, idxs = _build_sequences(df, seq_len=5)
    assert X.shape == (7, 5)
    assert len(y) == 7
    assert len(idxs) == 7
    assert y[0] == 5.0


def test_train_lstm_disabled_by_default():
    """LSTM training returns empty dict when disabled in config."""
    df = pd.DataFrame(
        {
            "player_id": ["p1"] * 30,
            "stat_type": ["points"] * 30,
            "game_date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "actual_value": np.random.default_rng(0).normal(20, 3, 30),
        }
    )
    assert train_lstm_form_features(df) == {}


def test_apply_lstm_features_merges_columns():
    """LSTM feature dict merges into feature frame by index."""
    df = pd.DataFrame({"actual_value": [1.0, 2.0]}, index=[10, 11])
    feats = {
        10: {
            "lstm_pred_actual_value": 1.5,
            "lstm_uncertainty": 0.1,
            "lstm_form_embedding_0": 0.2,
        }
    }
    out = apply_lstm_features_to_frame(df, feats)
    assert out.loc[10, "lstm_pred_actual_value"] == 1.5
    assert out.loc[11, "lstm_pred_actual_value"] == 0.0
