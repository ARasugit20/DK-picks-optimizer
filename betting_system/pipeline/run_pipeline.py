"""End-to-end pipeline orchestrator: ingest -> features -> train -> predict."""

from __future__ import annotations

import argparse
import shutil
from datetime import date, timedelta
from pathlib import Path

import joblib
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger
from betting_system.pipeline.features import build_features
from betting_system.pipeline.fixtures_loader import materialize_dry_run_fixtures
from betting_system.pipeline.ingest import ingest_odds_nba_player_props
from betting_system.pipeline.ingest_stats import ingest_nba_stats
from betting_system.pipeline.line_shop import select_best_lines
from betting_system.pipeline.player_mapping import (
    apply_player_map,
    build_player_id_map,
    validate_join_rate,
)
from betting_system.pipeline.predict_slate import generate_picks_today
from betting_system.pipeline.train import train_market_type


logger = get_logger(__name__)

MARKET_TYPE = "player_points_over"


def _ids_already_mapped(odds_df: pd.DataFrame, stat_df: pd.DataFrame) -> bool:
    """True when odds player_id values already exist in stat_results."""
    stat_ids = set(stat_df["player_id"].astype(str))
    odds_ids = set(odds_df["player_id"].astype(str))
    return odds_ids.issubset(stat_ids) and len(odds_ids) > 0


def _prepare_odds(odds_df: pd.DataFrame, stat_df: pd.DataFrame) -> pd.DataFrame:
    """Apply player mapping, validate join rate, and line-shop best prices."""
    if not _ids_already_mapped(odds_df, stat_df):
        map_df = build_player_id_map(odds_df, stat_df)
        odds_df = apply_player_map(odds_df, map_df)
    min_rate = float(load_settings().raw.get("mapping", {}).get("min_join_rate", 0.3))
    if not odds_df.empty:
        validate_join_rate(odds_df, stat_df, min_rate=min_rate if min_rate < 1 else 0.3)
    return select_best_lines(odds_df)


def _train_dry_run(features_path: Path, *, holdout_start: date) -> Path:
    """Train a lightweight calibrated model for dry-run (fast, small data)."""
    settings = load_settings()
    artifacts = train_market_type(
        features_path=features_path,
        market_type=MARKET_TYPE,
        holdout_start=holdout_start,
        min_rows=100,
        optuna_trials=2,
    )
    models_dir = Path(settings.data["processed_data_path"]) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_out = models_dir / "model.pkl"
    shutil.copy2(artifacts.lgbm_calibrated_path, model_out)
    return model_out


def _train_quick_fallback(features_path: Path) -> Path:
    """Fallback trainer when temporal split fails on tiny fixtures."""
    from betting_system.pipeline.train import _select_features

    settings = load_settings()
    seed = int(settings.model["random_seed"])
    df = pd.read_parquet(features_path)
    df = df[df["market_type"] == MARKET_TYPE]
    X, y = _select_features(df)
    base = LGBMClassifier(n_estimators=50, learning_rate=0.1, random_state=seed)
    cal = CalibratedClassifierCV(base, method="isotonic", cv=3)
    cal.fit(X, y)
    models_dir = Path(settings.data["processed_data_path"]) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_out = models_dir / "model.pkl"
    joblib.dump(cal, model_out)
    return model_out


def _holdout_start_from_features(features_path: Path) -> date:
    """Pick a holdout date inside the feature timeline for walk-forward training."""
    df = pd.read_parquet(features_path)
    max_d = pd.to_datetime(df["game_date"]).max().date()
    return max_d - timedelta(days=21)


def run_pipeline(*, dry_run: bool = False, bankroll: float = 1000.0) -> Path:
    """Execute full pipeline and return path to picks_today.json."""
    settings = load_settings()
    processed = Path(settings.data["processed_data_path"])
    processed.mkdir(parents=True, exist_ok=True)

    if dry_run:
        logger.info("Dry-run: using synthetic fixtures")
        stat_path, odds_path = materialize_dry_run_fixtures(processed / "dry_run")
        stat_df = pd.read_parquet(stat_path)
        odds_df = pd.read_parquet(odds_path)
        odds_df = _prepare_odds(odds_df, stat_df)
        odds_df.to_parquet(odds_path, index=False)
    else:
        season = settings.raw.get("stats", {}).get("season", "2024-25")
        stat_path = ingest_nba_stats(season=season, no_lines=True)
        stat_df = pd.read_parquet(stat_path)
        today = date.today().isoformat()
        odds_path = ingest_odds_nba_player_props(date=today)
        odds_df = pd.read_parquet(odds_path)
        odds_df = _prepare_odds(odds_df, stat_df)
        shopped_path = processed / "odds_shopped.parquet"
        odds_df.to_parquet(shopped_path, index=False)
        odds_path = shopped_path

    features_path = build_features(
        stat_results_path=stat_path,
        odds_parquet_path=odds_path,
        out_path=processed / "features.parquet",
    )
    holdout_start = _holdout_start_from_features(features_path)

    try:
        model_path = _train_dry_run(features_path, holdout_start=holdout_start) if dry_run else None
        if model_path is None:
            artifacts = train_market_type(
                features_path=features_path,
                market_type=MARKET_TYPE,
                holdout_start=holdout_start,
            )
            models_dir = Path(settings.data["processed_data_path"]) / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            model_path = models_dir / "model.pkl"
            shutil.copy2(artifacts.lgbm_calibrated_path, model_path)
    except ValueError as exc:
        if not dry_run:
            raise
        logger.warning("Dry-run train fallback: %s", exc)
        model_path = _train_quick_fallback(features_path)

    return generate_picks_today(
        features_path=features_path,
        model_path=model_path,
        market_type=MARKET_TYPE,
        bankroll=bankroll,
    )


def main() -> None:
    """CLI entrypoint for dk-pipeline."""
    parser = argparse.ArgumentParser(description="Run DK probabilistic forecasting pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Use fixtures instead of live API")
    parser.add_argument("--bankroll", type=float, default=1000.0, help="Capital allocation baseline")
    args = parser.parse_args()
    out = run_pipeline(dry_run=args.dry_run, bankroll=args.bankroll)
    logger.info("Pipeline complete -> %s", out)


if __name__ == "__main__":
    main()
