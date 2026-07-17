"""Contextual and rolling feature engineering for prop forecasting."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger
from betting_system.pipeline.sequence_features import apply_lstm_features_to_frame, train_lstm_form_features


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


def _add_minutes_features(df: pd.DataFrame, stat_df: pd.DataFrame) -> pd.DataFrame:
    """Add minutes_proxy and rolling minute features from game logs."""
    if "minutes" not in stat_df.columns:
        df["minutes_proxy"] = 0.0
        df["minutes_roll_mean_5"] = 0.0
        df["minutes_roll_mean_10"] = 0.0
        return df

    mins = stat_df[["player_id", "game_date", "minutes"]].drop_duplicates()
    mins["game_date"] = pd.to_datetime(mins["game_date"]).dt.date
    mins = mins.sort_values(["player_id", "game_date"])
    mins = _rolling_features(
        mins,
        group_cols=["player_id"],
        value_col="minutes",
        windows=[5, 10],
        ewm_span=5,
    )
    mins["minutes_proxy"] = mins["minutes_roll_mean_10"].fillna(mins["minutes"])
    keep = ["player_id", "game_date", "minutes_proxy", "minutes_roll_mean_5", "minutes_roll_mean_10"]
    df = df.merge(mins[keep], on=["player_id", "game_date"], how="left")
    df["minutes_proxy"] = df["minutes_proxy"].fillna(df["minutes_roll_mean_5"]).fillna(0.0)
    df["minutes_roll_mean_5"] = df["minutes_roll_mean_5"].fillna(0.0)
    df["minutes_roll_mean_10"] = df["minutes_roll_mean_10"].fillna(0.0)
    return df


def _add_opponent_defense_features(df: pd.DataFrame, stat_df: pd.DataFrame) -> pd.DataFrame:
    """Compute opponent defensive rank vs stat type using past games only."""
    if "opponent_team_abbr" not in stat_df.columns:
        df["opp_stat_allowed_roll_mean_10"] = 0.0
        df["opp_def_rank_vs_stat"] = 0.5
        return df

    team_allowed = stat_df[
        ["game_date", "opponent_team_abbr", "stat_type", "actual_value"]
    ].copy()
    team_allowed["game_date"] = pd.to_datetime(team_allowed["game_date"]).dt.date
    team_allowed = team_allowed.rename(columns={"opponent_team_abbr": "defense_team"})
    team_allowed = team_allowed.sort_values(["defense_team", "stat_type", "game_date"])

    team_allowed["opp_stat_allowed_roll_mean_10"] = team_allowed.groupby(
        ["defense_team", "stat_type"]
    )["actual_value"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).mean())

    stat_with_opp = stat_df[["game_id", "player_id", "stat_type", "game_date", "opponent_team_abbr"]].copy()
    stat_with_opp["game_date"] = pd.to_datetime(stat_with_opp["game_date"]).dt.date
    stat_with_opp = stat_with_opp.rename(columns={"opponent_team_abbr": "defense_team"})
    stat_with_opp = stat_with_opp.merge(
        team_allowed[["defense_team", "stat_type", "game_date", "opp_stat_allowed_roll_mean_10"]],
        on=["defense_team", "stat_type", "game_date"],
        how="left",
    )

    stat_with_opp["opp_stat_allowed_roll_mean_10"] = stat_with_opp["opp_stat_allowed_roll_mean_10"].fillna(
        stat_with_opp.groupby(["defense_team", "stat_type"])["opp_stat_allowed_roll_mean_10"].transform("median")
    ).fillna(0.0)

    def _rank_pct(group: pd.Series) -> pd.Series:
        return group.rank(pct=True, method="average")

    stat_with_opp["opp_def_rank_vs_stat"] = stat_with_opp.groupby(
        ["stat_type", "game_date"]
    )["opp_stat_allowed_roll_mean_10"].transform(_rank_pct)

    merge_cols = ["game_id", "player_id", "stat_type", "opp_stat_allowed_roll_mean_10", "opp_def_rank_vs_stat"]
    df = df.merge(stat_with_opp[merge_cols], on=["game_id", "player_id", "stat_type"], how="left")
    df["opp_stat_allowed_roll_mean_10"] = df["opp_stat_allowed_roll_mean_10"].fillna(0.0)
    df["opp_def_rank_vs_stat"] = df["opp_def_rank_vs_stat"].fillna(0.5)
    return df


def build_features(
    *,
    stat_results_path: str | Path,
    odds_parquet_path: str | Path,
    out_path: str | Path | None = None,
) -> Path:
    """Build leakage-free player-game feature rows for training and inference."""
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
    odds_df = odds_df.copy()
    odds_df["stat_type"] = (
        odds_df["market_type"]
        .str.replace("player_", "", regex=False)
        .str.replace("_over", "", regex=False)
        .str.replace("_under", "", regex=False)
    )

    stat_cols = ["game_id", "player_id", "stat_type", "actual_value", "hit", "game_date"]
    for c in ("minutes", "opponent_team_abbr", "player_name", "team_abbr"):
        if c in stat_df.columns:
            stat_cols.append(c)

    df = odds_df.merge(stat_df[stat_cols], on=["game_id", "player_id", "stat_type"], how="inner")

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
    df = _add_minutes_features(df, stat_df)
    df = _add_opponent_defense_features(df, stat_df)

    lstm_feats = train_lstm_form_features(stat_df)
    if lstm_feats:
        df = apply_lstm_features_to_frame(df, lstm_feats)

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
        "minutes_proxy",
        "minutes_roll_mean_5",
        "minutes_roll_mean_10",
        "opp_stat_allowed_roll_mean_10",
        "opp_def_rank_vs_stat",
    ]
    for c in ["lstm_pred_actual_value", "lstm_uncertainty"]:
        if c in df.columns:
            keep_cols.append(c)
    keep_cols.extend([c for c in df.columns if c.startswith("lstm_form_embedding_")])

    df = df[[c for c in keep_cols if c in df.columns]].copy()

    out_path = Path(out_path) if out_path is not None else processed_dir / "features.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("Wrote features parquet: %s (rows=%d)", out_path, len(df))
    return out_path
