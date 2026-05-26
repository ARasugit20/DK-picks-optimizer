from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from betting_system.config import load_settings
from betting_system.logging_utils import append_jsonl, get_logger, utcnow
from betting_system.pipeline.predict import compute_edge
from betting_system.optimizer.portfolio import optimize_slate


logger = get_logger(__name__)


@dataclass
class BacktestResult:
    roi: float
    total_staked: float
    total_profit: float
    max_drawdown: float
    weeks: int


def _load_models_for_market(models_dir: Path, market_type: str) -> tuple[Any, Any]:
    # naive: load latest by filename sort
    lgbms = sorted(models_dir.glob(f"lgbm_{market_type}_v1_*.joblib"))
    xgbs = sorted(models_dir.glob(f"xgb_{market_type}_v1_*.joblib"))
    if not lgbms or not xgbs:
        raise FileNotFoundError(f"Missing model artifacts for {market_type} in {models_dir}")
    return joblib.load(lgbms[-1]), joblib.load(xgbs[-1])


def _predict_p_hit(model_cal: Any, model_xgb: Any, X: pd.DataFrame) -> np.ndarray:
    p1 = model_cal.predict_proba(X)[:, 1]
    p2 = model_xgb.predict_proba(X)[:, 1]
    return (p1 + p2) / 2.0


def walk_forward_backtest(
    *,
    features_path: str | Path,
    market_type: str,
    bankroll_start: float = 1000.0,
    holdout_start: date,
    out_jsonl: str | Path | None = None,
) -> BacktestResult:
    settings = load_settings()
    models_dir = Path(settings.data["models_path"]) / "leg_model"
    out_jsonl = Path(out_jsonl) if out_jsonl else Path(settings.data["processed_data_path"]) / "backtest_log.jsonl"

    df = pd.read_parquet(features_path)
    df = df[df["market_type"] == market_type].copy()
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    df = df.sort_values("game_date")

    holdout_df = df[df["game_date"] >= holdout_start].copy()
    if holdout_df.empty:
        raise ValueError("No holdout rows for backtest. Check holdout_start.")

    model_cal, model_xgb = _load_models_for_market(models_dir, market_type)

    # feature columns match training selection
    drop = {"hit", "game_id", "player_id", "game_date", "market_type", "actual_value"}
    X = holdout_df.drop(columns=[c for c in holdout_df.columns if c in drop])
    for c in X.columns:
        if X[c].dtype == "O":
            X[c] = pd.to_numeric(X[c], errors="coerce")
    X = X.fillna(0.0)

    p_hit = _predict_p_hit(model_cal, model_xgb, X)
    holdout_df["p_hit"] = p_hit

    # Compute edge per leg and filter worthy legs per date (slate)
    bankroll = bankroll_start
    bankroll_curve = []
    peak = bankroll
    max_dd = 0.0
    total_staked = 0.0
    total_profit = 0.0

    for d, day_df in holdout_df.groupby("game_date"):
        worthy = []
        for _, r in day_df.iterrows():
            er = compute_edge(float(r["p_hit"]), int(r["odds_american"]))
            if not er.worthy:
                continue
            worthy.append(
                {
                    "game_id": str(r["game_id"]),
                    "market_type": str(r["market_type"]),
                    "player_id": str(r["player_id"]),
                    "line": float(r["line"]),
                    "odds_american": int(r["odds_american"]),
                    "p_hit": float(er.p_hit),
                    "edge": float(er.edge),
                    "ev_per_unit": float(er.ev_per_unit),
                    "hit": bool(r["hit"]),
                }
            )

        slate = optimize_slate(slate_id=str(d), worthy_legs=worthy, bankroll=bankroll, corr_path=None)

        # Simulate: parlay hits if all legs hit
        day_profit = 0.0
        day_staked = 0.0
        for parlay in slate.parlays:
            stake = float(parlay.stake)
            day_staked += stake
            legs_hit = all(next(l for l in worthy if l["game_id"] == leg.game_id and l["player_id"] == leg.player_id and l["market_type"] == leg.market_type)["hit"] for leg in parlay.legs)
            if legs_hit:
                payout = float(parlay.expected_payout)
                day_profit += payout - stake
            else:
                day_profit -= stake

        bankroll += day_profit
        total_profit += day_profit
        total_staked += day_staked
        peak = max(peak, bankroll)
        dd = (peak - bankroll) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        bankroll_curve.append({"date": str(d), "bankroll": bankroll, "profit": day_profit, "staked": day_staked})

        append_jsonl(
            out_jsonl,
            {
                "slate_id": str(d),
                "bankroll": bankroll,
                "profit": day_profit,
                "staked": day_staked,
                "parlays": [p.model_dump() for p in slate.parlays],
            },
        )

    roi = (total_profit / total_staked) if total_staked > 0 else 0.0
    return BacktestResult(
        roi=float(roi),
        total_staked=float(total_staked),
        total_profit=float(total_profit),
        max_drawdown=float(max_dd),
        weeks=int(settings.backtest["walk_forward_weeks"]),
    )

