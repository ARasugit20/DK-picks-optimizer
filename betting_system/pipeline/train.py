from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import optuna
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import log_loss
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBClassifier

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger, utcnow


logger = get_logger(__name__)


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.digitize(y_prob, bins) - 1
    ece = 0.0
    for b in range(n_bins):
        mask = idx == b
        if not np.any(mask):
            continue
        acc = float(np.mean(y_true[mask]))
        conf = float(np.mean(y_prob[mask]))
        ece += (np.sum(mask) / len(y_true)) * abs(acc - conf)
    return float(ece)


def _time_split(df: pd.DataFrame, holdout_start: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("game_date").copy()
    train = df[df["game_date"] < holdout_start].copy()
    valid = df[df["game_date"] >= holdout_start].copy()
    return train, valid


def _select_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    y = df["hit"].astype(int)
    drop = {"hit", "game_id", "player_id", "game_date", "market_type", "actual_value"}
    X = df.drop(columns=[c for c in df.columns if c in drop])
    # ensure numeric
    for c in X.columns:
        if X[c].dtype == "O":
            X[c] = pd.to_numeric(X[c], errors="coerce")
    X = X.fillna(0.0)
    return X, y


def _optuna_objective(X: pd.DataFrame, y: pd.Series, seed: int) -> Any:
    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 200, 1200),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 16, 255),
            "max_depth": trial.suggest_int("max_depth", -1, 12),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 200),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
            "random_state": seed,
            "n_jobs": -1,
        }

        tscv = TimeSeriesSplit(n_splits=5)
        losses = []
        for tr_idx, va_idx in tscv.split(X):
            X_tr, X_va = X.iloc[tr_idx], X.iloc[va_idx]
            y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]
            m = LGBMClassifier(**params)
            m.fit(X_tr, y_tr)
            p = m.predict_proba(X_va)[:, 1]
            losses.append(log_loss(y_va, p, labels=[0, 1]))
        return float(np.mean(losses))

    return objective


@dataclass
class TrainedArtifacts:
    lgbm_calibrated_path: Path
    xgb_path: Path
    metrics_path: Path


def train_market_type(
    *,
    features_path: str | Path,
    market_type: str,
    holdout_start: date,
) -> TrainedArtifacts:
    settings = load_settings()
    seed = int(settings.model["random_seed"])
    trials = int(settings.training["optuna_trials"])
    calib_cfg = settings.training["calibration"]
    ece_threshold = float(calib_cfg["ece_threshold"])
    primary_method = str(calib_cfg["primary_method"])
    fallback_method = str(calib_cfg["fallback_method"])

    df = pd.read_parquet(features_path)
    df = df[df["market_type"] == market_type].copy()
    if len(df) < 500:
        raise ValueError(f"Not enough rows to train {market_type}: {len(df)} (need ~500+)")

    train_df, valid_df = _time_split(df, holdout_start=holdout_start)
    if train_df.empty or valid_df.empty:
        raise ValueError("Temporal split produced empty train or validation set. Check holdout_start/game_date.")

    X_train, y_train = _select_features(train_df)
    X_valid, y_valid = _select_features(valid_df)

    logger.info("Optuna tuning LightGBM for %s (trials=%d)", market_type, trials)
    study = optuna.create_study(direction="minimize")
    study.optimize(_optuna_objective(X_train, y_train, seed), n_trials=trials)
    best = study.best_params
    best.update({"random_state": seed, "n_jobs": -1})

    base_lgbm = LGBMClassifier(**best)
    # Calibrate via CV on training set
    cal = CalibratedClassifierCV(base_lgbm, method=primary_method, cv=5)
    cal.fit(X_train, y_train)
    p_valid = cal.predict_proba(X_valid)[:, 1]
    ll_valid = log_loss(y_valid, p_valid, labels=[0, 1])
    ece = expected_calibration_error(y_valid.to_numpy(), p_valid)

    if ece > ece_threshold:
        logger.warning("ECE %.4f exceeded threshold %.4f, falling back to %s", ece, ece_threshold, fallback_method)
        cal = CalibratedClassifierCV(base_lgbm, method=fallback_method, cv=5)
        cal.fit(X_train, y_train)
        p_valid = cal.predict_proba(X_valid)[:, 1]
        ll_valid = log_loss(y_valid, p_valid, labels=[0, 1])
        ece = expected_calibration_error(y_valid.to_numpy(), p_valid)

    # XGBoost ensemble (uncalibrated for v1, averaged at inference time)
    xgb = XGBClassifier(
        n_estimators=800,
        learning_rate=0.03,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=seed,
        n_jobs=-1,
        eval_metric="logloss",
    )
    xgb.fit(X_train, y_train)
    p_xgb = xgb.predict_proba(X_valid)[:, 1]
    ll_xgb = log_loss(y_valid, p_xgb, labels=[0, 1])

    ts = utcnow().date().isoformat()
    models_dir = Path(settings.data["models_path"]) / "leg_model"
    models_dir.mkdir(parents=True, exist_ok=True)
    lgbm_path = models_dir / f"lgbm_{market_type}_v1_{ts}.joblib"
    xgb_path = models_dir / f"xgb_{market_type}_v1_{ts}.joblib"
    metrics_path = models_dir / f"metrics_{market_type}_v1_{ts}.json"

    joblib.dump(cal, lgbm_path)
    joblib.dump(xgb, xgb_path)
    metrics = {
        "market_type": market_type,
        "trained_at": utcnow().isoformat(),
        "holdout_start": holdout_start.isoformat(),
        "val_log_loss_lgbm_cal": float(ll_valid),
        "val_ece_lgbm_cal": float(ece),
        "val_log_loss_xgb": float(ll_xgb),
        "optuna_best_params": best,
    }
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    logger.info("Saved artifacts: %s %s", lgbm_path.name, xgb_path.name)
    return TrainedArtifacts(lgbm_calibrated_path=lgbm_path, xgb_path=xgb_path, metrics_path=metrics_path)

