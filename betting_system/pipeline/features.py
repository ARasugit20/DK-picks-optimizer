from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger


logger = get_logger(__name__)


def _rolling_features(
    df: pd.DataFrame,
    *,
    group_cols: list[str],
    value_col: str,
    windows: list[int],
    ewm_span: int = 5,
) -> pd.DataFrame:
    """
    All rolling/EWM features are shifted by 1 to prevent leakage.
    """
    df = df.sort_values(group_cols + ["game_date"]).copy()
    g = df.groupby(group_cols, sort=False)

    for w in windows:
        df[f"{value_col}_roll_mean_{w}"] = g[value_col].transform(lambda s: s.shift(1).rolling(w, min_periods=1).mean())

    df[f"{value_col}_ewm_mean_span_{ewm_span}"] = g[value_col].transform(
        lambda s: s.shift(1).ewm(span=ewm_span, adjust=False).mean()
    )
    return df


def build_features(
    *,
    stat_results_path: str | Path,
    odds_parquet_path: str | Path,
    out_path: str | Path | None = None,
) -> Path:
    """
    Build player-game feature rows by joining:
    - stat results (must include: game_id, player_id, stat_type, actual_value, hit, game_date)
    - odds records (must include: game_id, player_id, market_type, line, implied_prob, ingested_at)

    Output is leakage-free features parquet for training & backtesting.
    """
    settings = load_settings()
    processed_dir = Path(settings.data["processed_data_path"])
    processed_dir.mkdir(parents=True, exist_ok=True)

    stat_df = pd.read_parquet(stat_results_path) if str(stat_results_path).endswith(".parquet") else pd.read_csv(stat_results_path)
    odds_df = pd.read_parquet(odds_parquet_path)

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

    # Join odds to results (the modeling unit is "a posted line for a player")
    df = odds_df.merge(
        stat_df[["game_id", "player_id", "stat_type", "actual_value", "hit", "game_date"]],
        on=["game_id", "player_id"],
        how="inner",
    )

    # Derive target stat column name (simple mapping; can expand per market family)
    # Example market_type: "player_points_over" -> stat_type "points"
    df["market_family"] = df["market_type"].str.replace("_over", "").str.replace("_under", "", regex=False)
    df["is_over"] = df["market_type"].str.contains("_over")

    # Basic features
    df["line_minus_recent"] = np.nan

    feat_cfg = settings.features
    rolling_windows = list(feat_cfg.get("rolling_windows", [3, 5, 10]))
    ewm_span = int(feat_cfg.get("ewm_span", 5))
    season_games = float(feat_cfg.get("season_games", 82))

    # Leakage-free rolling features computed on actual_value within stat_type
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

    # Season progress: within each player/stat_type
    df["game_number_season"] = df.groupby(["player_id", "stat_type"])["game_date"].rank(method="dense").astype(int)
    df["season_progress"] = (df["game_number_season"] / season_games).clip(0, 1)

    # Placeholder contextual features (wired for later enrichment)
    for col in ["home_away", "days_rest", "back_to_back", "opp_def_rank_vs_stat", "minutes_proxy"]:
        if col not in df.columns:
            df[col] = np.nan

    # Opening odds feature: choose earliest ingested odds per (game_id, market_type, player_id, line)
    df["opening_implied_prob"] = df.groupby(["game_id", "market_type", "player_id", "line"])["implied_prob"].transform("first")
    df["opening_odds_american"] = df.groupby(["game_id", "market_type", "player_id", "line"])["odds_american"].transform("first")

    # Line movement placeholder: closing - opening (if we later set is_closing and have closing lines)
    if "is_closing" in df.columns:
        # default: 0 if no closing lines present
        open_line = df.groupby(["game_id", "market_type", "player_id"])["line"].transform("first")
        close_line = df.groupby(["game_id", "market_type", "player_id"])["line"].transform("last")
        df["line_movement"] = close_line - open_line
    else:
        df["line_movement"] = 0.0

    # Target: "hit" already computed in stat_results.
    # NOTE: For unders, hit definition differs; v1 assumes stat_results computed per-market correctly.

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

