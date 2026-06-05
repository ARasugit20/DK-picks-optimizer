"""Contextual and rolling feature engineering for prop forecasting."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger


logger = get_logger(__name__)

_HOME_AWAY_MAP = {"home": 1.0, "away": 0.0, "H": 1.0, "A": 0.0, 1: 1.0, 0: 0.0}


def _rolling_features(
    df: pd.DataFrame,
    *,
    group_cols: list[str],
    value_col: str,
    windows: list[int],
    ewm_span: int = 5,
) -> pd.DataFrame:
    """Compute rolling/EWM aggregates shifted by 1 to prevent leakage."""
    df = df.sort_values(group_cols + ["game_date"]).copy()
    g = df.groupby(group_cols, sort=False)

    for w in windows:
        df[f"{value_col}_roll_mean_{w}"] = g[value_col].transform(
            lambda s: s.shift(1).rolling(w, min_periods=1).mean()
        )

    df[f"{value_col}_ewm_mean_span_{ewm_span}"] = g[value_col].transform(
        lambda s: s.shift(1).ewm(span=ewm_span, adjust=False).mean()
    )
    return df


def _encode_home_away(series: pd.Series) -> pd.Series:
    """Map home/away labels to numeric 1/0."""
    return series.map(lambda v: _HOME_AWAY_MAP.get(v, _HOME_AWAY_MAP.get(str(v).lower(), np.nan)))


def _add_contextual_features(df: pd.DataFrame, stat_df: pd.DataFrame) -> pd.DataFrame:
    """Attach home_away, days_rest, and back_to_back from stat game history."""
    stat_ctx = stat_df[
        ["game_id", "player_id", "game_date"]
        + [c for c in ("home_away",) if c in stat_df.columns]
    ].drop_duplicates()

    if "home_away" in stat_ctx.columns:
        stat_ctx = stat_ctx.copy()
        stat_ctx["home_away"] = _encode_home_away(stat_ctx["home_away"])
    elif "home_away" in df.columns:
        stat_ctx["home_away"] = _encode_home_away(df.groupby(["game_id", "player_id"])["home_away"].transform("first"))
    else:
        stat_ctx["home_away"] = 0.5

    df = df.merge(stat_ctx[["game_id", "player_id", "home_away"]], on=["game_id", "player_id"], how="left")

    sched = stat_df[["player_id", "game_date"]].drop_duplicates().sort_values(["player_id", "game_date"])
    sched["game_date"] = pd.to_datetime(sched["game_date"])
    sched["days_rest"] = sched.groupby("player_id")["game_date"].diff().dt.days
    sched["days_rest"] = sched["days_rest"].fillna(3).clip(lower=0)
    sched["game_date"] = sched["game_date"].dt.date
    df = df.merge(sched[["player_id", "game_date", "days_rest"]], on=["player_id", "game_date"], how="left")
    df["days_rest"] = df["days_rest"].fillna(3)
    df["back_to_back"] = (df["days_rest"] == 1).astype(int)

    return df


def build_features(
    *,
    stat_results_path: str | Path,
    odds_parquet_path: str | Path,
    out_path: str | Path | None = None,
) -> Path:
    """Build leakage-free player-game feature rows for training and inference.

    Joins stat results with posted odds, adds shift-1 rolling stats and contextual
    fields (home_away, days_rest, back_to_back).

    Args:
        stat_results_path: Parquet/CSV with game_id, player_id, stat_type, actual_value,
            hit, game_date, and optional home_away.
        odds_parquet_path: Parquet with game_id, player_id, market_type, line,
            implied_prob, ingested_at, odds_american.
        out_path: Optional output parquet path.

    Returns:
        Path to written features parquet.
    """
    settings = load_settings()
    processed_dir = Path(settings.data["processed_data_path"])
    processed_dir.mkdir(parents=True, exist_ok=True)

    stat_df = pd.read_parquet(stat_results_path) if str(stat_results_path).endswith(".parquet") else pd.read_csv(stat_results_path)
    odds_df = pd.read_parquet(odds_parquet_path)
    if "home_away" in odds_df.columns:
        odds_df = odds_df.drop(columns=["home_away"])

    required_stat = {"game_id", "player_id", "stat_type", "actual_value", "hit", "game_date"}
    missing = required_stat - set(stat_df.columns)
    if missing:
        raise ValueError(f"stat_results missing required columns: {sorted(missing)}")

    required_odds = {"game_id", "player_id", "market_type", "line", "implied_prob", "ingested_at", "odds_american"}
    missing = required_odds - set(odds_df.columns)
    if missing:
        raise ValueError(f"odds parquet missing required columns: {sorted(missing)}")

    stat_df["game_date"] = pd.to_datetime(stat_df["game_date"]).dt.date
    odds_df["ingested_at"] = pd.to_datetime(odds_df["ingested_at"])

    df = odds_df.merge(
        stat_df[["game_id", "player_id", "stat_type", "actual_value", "hit", "game_date"]],
        on=["game_id", "player_id"],
        how="inner",
    )

    df["market_family"] = df["market_type"].str.replace("_over", "").str.replace("_under", "", regex=False)
    df["is_over"] = df["market_type"].str.contains("_over")
    df["line_minus_recent"] = np.nan

    feat_cfg = settings.features
    rolling_windows = list(feat_cfg.get("rolling_windows", [3, 5, 10]))
    ewm_span = int(feat_cfg.get("ewm_span", 5))
    season_games = float(feat_cfg.get("season_games", 82))

    df = df.sort_values(["player_id", "stat_type", "game_date"]).copy()
    df = _rolling_features(
        df,
        group_cols=["player_id", "stat_type"],
        value_col="actual_value",
        windows=rolling_windows,
        ewm_span=ewm_span,
    )
    roll_col = f"actual_value_roll_mean_{rolling_windows[1] if len(rolling_windows) > 1 else rolling_windows[0]}"
    df["line_minus_recent"] = df["line"] - df[roll_col]

    df["game_number_season"] = df.groupby(["player_id", "stat_type"])["game_date"].rank(method="dense").astype(int)
    df["season_progress"] = (df["game_number_season"] / season_games).clip(0, 1)

    df = _add_contextual_features(df, stat_df)

    for col in ["opp_def_rank_vs_stat", "minutes_proxy"]:
        if col not in df.columns:
            df[col] = 0.0

    df["opening_implied_prob"] = df.groupby(["game_id", "market_type", "player_id", "line"])["implied_prob"].transform("first")
    df["opening_odds_american"] = df.groupby(["game_id", "market_type", "player_id", "line"])["odds_american"].transform("first")

    if "is_closing" in df.columns:
        open_line = df.groupby(["game_id", "market_type", "player_id"])["line"].transform("first")
        close_line = df.groupby(["game_id", "market_type", "player_id"])["line"].transform("last")
        df["line_movement"] = close_line - open_line
    else:
        df["line_movement"] = 0.0

    keep_cols = [
        "game_id",
        "game_date",
        "player_id",
        "market_type",
        "line",
        "odds_american",
        "opening_implied_prob",
        "opening_odds_american",
        "line_movement",
        "actual_value",
        "hit",
        "actual_value_roll_mean_3",
        "actual_value_roll_mean_5",
        "actual_value_roll_mean_10",
        "actual_value_ewm_mean_span_5",
        "line_minus_recent",
        "game_number_season",
        "season_progress",
        "home_away",
        "days_rest",
        "back_to_back",
        "opp_def_rank_vs_stat",
        "minutes_proxy",
    ]
    df = df[keep_cols].copy()

    out_path = Path(out_path) if out_path is not None else processed_dir / "features.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("Wrote features parquet: %s (rows=%d)", out_path, len(df))
    return out_path
