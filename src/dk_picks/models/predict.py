import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from dk_picks.config import settings
from dk_picks.features.build import FEATURE_COLS, build_feature_matrix
from dk_picks.odds import expected_value


def load_model(sport: str, market: str = "h2h") -> dict:
    slug = f"{sport}_{market}".replace(" ", "_")
    path = settings.artifacts_dir / f"{slug}.joblib"
    if not path.exists():
        raise FileNotFoundError(f"No model at {path}. Run: dk-picks train --sport {sport}")
    return joblib.load(path)


def _heuristic_prob(row) -> float:
    x = (
        0.08 * row["team_rating_edge"]
        + 1.2 * row["team_win_edge"]
        + 0.02 * row["rest_edge"]
        + 0.03 * row["home_court"]
    )
    if row["market"] == "totals":
        x = 0.2 * row["team_rating_edge"]
    return 1.0 / (1.0 + math.exp(-x))


def predict_proba(sport: str, market: str = "h2h") -> pd.DataFrame:
    bundle = load_model(sport, market)
    model = bundle["model"]
    features = bundle.get("features", FEATURE_COLS)

    df = build_feature_matrix(sport)
    if df.empty:
        return df
    df = df[df["market"] == market].copy()
    X = df[features].fillna(0)
    proba = model.predict_proba(X)[:, 1]
    # Blend with heuristic when ML output is degenerate (tiny training slate)
    heur = df.apply(_heuristic_prob, axis=1)
    if (proba < 0.02).all() or (proba > 0.98).all():
        proba = 0.35 * proba + 0.65 * heur.values
    else:
        proba = 0.5 * proba + 0.5 * heur.values
    df["model_prob"] = proba
    df["edge"] = df["model_prob"] - df["fair_prob"]
    df["ev"] = [
        expected_value(p, int(a)) for p, a in zip(df["model_prob"], df["price_american"])
    ]
    return df.sort_values("edge", ascending=False)
