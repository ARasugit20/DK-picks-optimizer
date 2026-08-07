"""Integration tests proving calibration improves holdout reliability."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from betting_system.pipeline.train import train_market_type


MARKET_TYPES = [
    "player_points_over",
    "player_assists_over",
    "player_rebounds_over",
]


def _write_training_config(tmp_path: Path, repo_root: Path, *, ece_threshold: float | None = None) -> Path:
    raw = yaml.safe_load((repo_root / "betting_system" / "config.yaml").read_text(encoding="utf-8"))
    processed = tmp_path / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    raw["data"]["processed_data_path"] = str(processed) + "/"
    raw["data"]["models_path"] = str(processed / "models") + "/"
    raw["training"]["optuna_trials"] = 2
    if ece_threshold is not None:
        raw["training"]["calibration"]["ece_threshold"] = ece_threshold
    out = tmp_path / "config.yaml"
    out.write_text(yaml.dump(raw), encoding="utf-8")
    return out


def _synthetic_features(
    tmp_path: Path,
    *,
    market_type: str,
    n_rows: int = 600,
    seed: int = 42,
) -> Path:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n_rows, freq="D")
    player_ids = [f"p{i % 8}" for i in range(n_rows)]
    actual = rng.normal(20, 4, size=n_rows)
    line = actual + rng.normal(0, 1.5, size=n_rows)
    hit = (actual > line).astype(int)

    df = pd.DataFrame(
        {
            "game_date": [d.date() for d in dates],
            "hit": hit,
            "game_id": [f"g{i}" for i in range(n_rows)],
            "player_id": player_ids,
            "market_type": market_type,
            "actual_value": actual,
            "line": line,
            "odds_american": -110,
            "actual_value_roll_mean_3": rng.uniform(15, 25, size=n_rows),
            "actual_value_roll_mean_5": rng.uniform(15, 25, size=n_rows),
            "actual_value_roll_mean_10": rng.uniform(15, 25, size=n_rows),
            "actual_value_ewm_mean_span_5": rng.uniform(15, 25, size=n_rows),
            "line_minus_recent": rng.normal(0, 2, size=n_rows),
            "game_number_season": np.arange(1, n_rows + 1),
            "season_progress": np.linspace(0.05, 0.95, n_rows),
            "home_away": rng.integers(0, 2, size=n_rows),
            "days_rest": rng.integers(1, 4, size=n_rows),
            "back_to_back": rng.integers(0, 2, size=n_rows),
            "minutes_proxy": rng.uniform(24, 36, size=n_rows),
            "minutes_roll_mean_5": rng.uniform(24, 36, size=n_rows),
            "minutes_roll_mean_10": rng.uniform(24, 36, size=n_rows),
            "opp_stat_allowed_roll_mean_10": rng.uniform(18, 24, size=n_rows),
            "opp_def_rank_vs_stat": rng.uniform(0.2, 0.8, size=n_rows),
            "opening_implied_prob": rng.uniform(0.45, 0.55, size=n_rows),
            "opening_odds_american": -110,
            "line_movement": rng.normal(0, 0.5, size=n_rows),
        }
    )
    path = tmp_path / f"{market_type}.parquet"
    df.to_parquet(path, index=False)
    return path


@pytest.mark.parametrize("market_type", MARKET_TYPES)
def test_calibrated_holdout_ece_not_worse_than_uncalibrated(
    tmp_path: Path,
    repo_root: Path,
    market_type: str,
):
    """Calibrated holdout ECE should not exceed uncalibrated ECE per market type."""
    config_path = _write_training_config(tmp_path, repo_root)
    os.environ["BETTING_CONFIG_PATH"] = str(config_path)
    features_path = _synthetic_features(tmp_path, market_type=market_type)

    artifacts = train_market_type(
        features_path=features_path,
        market_type=market_type,
        holdout_start=date(2024, 4, 1),
        min_rows=120,
        optuna_trials=2,
    )
    metrics = __import__("json").loads(artifacts.metrics_path.read_text(encoding="utf-8"))

    assert metrics["val_ece_lgbm_cal"] <= metrics["val_ece_lgbm_uncal"] + 1e-6
    assert metrics["artifact_version"] == "1.0.0"
    assert metrics["config_fingerprint"]
    assert metrics["dataset_window"]["valid_rows"] > 0


def test_isotonic_fallback_to_sigmoid_when_threshold_breached(tmp_path: Path, repo_root: Path):
    """Training falls back to sigmoid when isotonic holdout ECE exceeds threshold."""
    config_path = _write_training_config(tmp_path, repo_root, ece_threshold=0.001)
    os.environ["BETTING_CONFIG_PATH"] = str(config_path)
    features_path = _synthetic_features(tmp_path, market_type="player_points_over", seed=7)

    artifacts = train_market_type(
        features_path=features_path,
        market_type="player_points_over",
        holdout_start=date(2024, 4, 1),
        min_rows=120,
        optuna_trials=2,
    )
    metrics = __import__("json").loads(artifacts.metrics_path.read_text(encoding="utf-8"))
    assert metrics["calibration_method"] == "sigmoid"
