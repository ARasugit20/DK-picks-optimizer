import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split

from dk_picks.config import load_thresholds, settings
from dk_picks.features.build import FEATURE_COLS, build_feature_matrix


def _synthetic_labels(df: pd.DataFrame) -> pd.Series:
    """Bootstrap training when no historical results yet: weak label from fair_prob + noise."""
    rng = np.random.default_rng(42)
    base = df["fair_prob"].values
    noise = rng.normal(0, 0.08, size=len(df))
    prob = np.clip(base + noise, 0.05, 0.95)
    return (rng.random(len(df)) < prob).astype(int)


def train_market_model(sport: str, market: str = "h2h", use_synthetic: bool = True) -> Path:
    df = build_feature_matrix(sport)
    if df.empty:
        raise ValueError("No odds data. Run: dk-picks ingest-odds --sport <sport>")

    df = df[df["market"] == market].copy()
    if df.empty:
        raise ValueError(f"No rows for market={market}")

    if "label" in df.columns and df["label"].notna().sum() >= 50:
        y = df["label"].astype(int)
        use_synthetic = False
    elif use_synthetic:
        y = _synthetic_labels(df)
    else:
        raise ValueError("Need at least 50 labeled rows or enable synthetic bootstrap")

    X = df[FEATURE_COLS].fillna(0)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    base = LGBMClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=5,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        verbose=-1,
    )
    model = CalibratedClassifierCV(base, method="isotonic", cv=3)
    model.fit(X_train, y_train)

    acc = (model.predict(X_test) == y_test).mean()
    thresholds = load_thresholds()
    min_samples = thresholds.get("backtest", {}).get("min_samples_per_market", 200)

    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    slug = f"{sport}_{market}".replace(" ", "_")
    out = settings.artifacts_dir / f"{slug}.joblib"
    meta_path = settings.artifacts_dir / f"{slug}.meta.json"

    joblib.dump({"model": model, "features": FEATURE_COLS, "market": market, "sport": sport}, out)
    meta_path.write_text(
        json.dumps(
            {
                "sport": sport,
                "market": market,
                "test_accuracy": float(acc),
                "n_train": int(len(X_train)),
                "synthetic_labels": use_synthetic,
                "min_samples_recommended": min_samples,
            },
            indent=2,
        )
    )
    return out
