"""Generate today's slate JSON for API and dashboard consumption."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger, utcnow
from betting_system.optimizer.portfolio import optimize_slate
from betting_system.pipeline.predict import compute_edge
from betting_system.pipeline.train import _select_features


logger = get_logger(__name__)


def _latest_slate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows for the most recent game_date in the feature frame."""
    df = df.copy()
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    latest = df["game_date"].max()
    return df[df["game_date"] == latest].copy()


def _predict_p_hit(model: Any, X: pd.DataFrame) -> np.ndarray:
    """Return calibrated positive-class probabilities."""
    return model.predict_proba(X)[:, 1]


def _leg_display_row(row: pd.Series, edge_result: Any) -> dict[str, Any]:
    """Map a feature row + edge result to dashboard/API leg dict."""
    side = "OVER" if "over" in str(row["market_type"]) else "UNDER"
    return {
        "game_id": str(row["game_id"]),
        "player_id": str(row["player_id"]),
        "player_name": str(row.get("player_name", row["player_id"])),
        "position": str(row.get("position", "")),
        "matchup": str(row.get("matchup", row["game_id"])),
        "market_type": str(row["market_type"]),
        "market_label": "PTS",
        "side": side,
        "line": float(row["line"]),
        "odds_american": int(row["odds_american"]),
        "p_hit": float(edge_result.p_hit),
        "edge": float(edge_result.edge),
        "ev_per_unit": float(edge_result.ev_per_unit),
        "worthy": bool(edge_result.worthy),
        "model_confidence_pct": round(float(edge_result.p_hit) * 100, 1),
        "home_away": row.get("home_away"),
        "days_rest": row.get("days_rest"),
        "back_to_back": row.get("back_to_back"),
    }


def generate_picks_today(
    *,
    features_path: str | Path,
    model_path: str | Path,
    market_type: str = "player_points_over",
    bankroll: float = 1000.0,
    out_path: str | Path | None = None,
) -> Path:
    """Score latest slate, optimize portfolios, and write picks_today.json."""
    settings = load_settings()
    processed = Path(settings.data["processed_data_path"])
    processed.mkdir(parents=True, exist_ok=True)
    out_path = Path(out_path) if out_path else processed / "picks_today.json"

    df = pd.read_parquet(features_path)
    df = df[df["market_type"] == market_type].copy()
    slate_df = _latest_slate_rows(df)
    if slate_df.empty:
        raise ValueError("No rows in latest slate for picks generation.")

    model = joblib.load(model_path)
    X, _ = _select_features(slate_df)
    p_hit = _predict_p_hit(model, X)

    worthy: list[dict[str, Any]] = []
    for idx, (_, row) in enumerate(slate_df.iterrows()):
        er = compute_edge(float(p_hit[idx]), int(row["odds_american"]))
        leg = _leg_display_row(row, er)
        if er.worthy or float(er.edge) > float(settings.model["min_edge"]):
            worthy.append(leg)

    slate_id = str(slate_df["game_date"].iloc[0])
    slate = optimize_slate(slate_id=slate_id, worthy_legs=worthy, bankroll=bankroll, corr_path=None)

    payload = {
        "slate_id": slate_id,
        "generated_at": utcnow().isoformat(),
        "bankroll": float(bankroll),
        "total_exposure": float(slate.total_exposure),
        "worthy_legs": worthy,
        "parlays": [p.model_dump() for p in slate.parlays],
    }
    out_path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    logger.info("Wrote picks_today.json (%d worthy legs)", len(worthy))
    return out_path
