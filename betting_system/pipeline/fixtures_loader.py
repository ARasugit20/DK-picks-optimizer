"""Dry-run fixture materialization for the end-to-end pipeline."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from betting_system.logging_utils import get_logger


logger = get_logger(__name__)

PLAYERS = [
    ("203081", "D. Lillard", "POR", "home"),
    ("203999", "N. Jokic", "DEN", "home"),
    ("1629639", "T. Herro", "MIA", "home"),
    ("1628369", "J. Tatum", "BOS", "away"),
    ("1628973", "J. Brunson", "NYK", "home"),
    ("1628368", "D. Fox", "SAC", "away"),
    ("1628983", "S. Gilgeous-Alexander", "OKC", "home"),
    ("1630162", "A. Edwards", "MIN", "away"),
]

OPPONENTS = ["LAL", "BOS", "MIA", "NYK", "DEN", "PHX", "DAL", "MEM"]


def _rng(seed: int) -> np.random.Generator:
    """Return a deterministic RNG for fixture generation."""
    return np.random.default_rng(seed)


def generate_stat_results(*, n_games: int = 80, seed: int = 42) -> pd.DataFrame:
    """Build synthetic stat results with minutes, opponent, and home_away."""
    rng = _rng(seed)
    rows: list[dict] = []
    base = date(2024, 10, 1)
    for game_idx in range(n_games):
        game_date = base + timedelta(days=game_idx * 2)
        game_id = f"00224{game_idx:05d}"
        opp = OPPONENTS[game_idx % len(OPPONENTS)]
        for player_id, name, team, home_away in PLAYERS:
            minutes = float(rng.integers(18, 38))
            for stat_type in ("points", "assists", "rebounds"):
                base_val = {"points": 22, "assists": 6, "rebounds": 8}[stat_type]
                actual = float(max(0, rng.normal(base_val, base_val * 0.25)))
                line = actual + rng.integers(-3, 4)
                hit = actual > line
                opponent = opp if home_away == "home" else team
                rows.append(
                    {
                        "game_id": game_id,
                        "player_id": player_id,
                        "player_name": name,
                        "team_id": team,
                        "team_abbr": team,
                        "opponent_team_abbr": opponent,
                        "stat_type": stat_type,
                        "actual_value": actual,
                        "hit": hit,
                        "game_date": game_date,
                        "minutes": minutes,
                        "home_away": home_away,
                        "season": "2024-25",
                    }
                )
    return pd.DataFrame(rows)


def generate_odds_props(stat_df: pd.DataFrame, *, seed: int = 42) -> pd.DataFrame:
    """Build odds rows aligned to stat results for dry-run ingest."""
    rng = _rng(seed)
    rows: list[dict] = []
    points = stat_df[stat_df["stat_type"] == "points"]
    for _, row in points.iterrows():
        line = float(row["actual_value"]) + rng.integers(-3, 4)
        odds_am = int(rng.choice([-125, -115, -110, -105, 100, 110]))
        implied = 100 / (100 + abs(odds_am)) if odds_am < 0 else 100 / (odds_am + 100)
        for book in ("draftkings", "fanduel", "caesars"):
            rows.append(
                {
                    "game_id": row["game_id"],
                    "player_id": row["player_id"],
                    "market_type": "player_points_over",
                    "line": line,
                    "odds_american": odds_am + rng.integers(-5, 6),
                    "implied_prob": float(implied),
                    "bookmaker": book,
                    "ingested_at": pd.Timestamp(f"{row['game_date']}T12:00:00Z"),
                    "is_closing": False,
                }
            )
    return pd.DataFrame(rows)


def write_nba_stats_fixture(out_path: Path) -> Path:
    """Write NBA stats fixture parquet for tests and --fixture mode."""
    df = generate_stat_results()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return out_path


def materialize_dry_run_fixtures(out_dir: Path) -> tuple[Path, Path]:
    """Write stat + odds parquet fixtures and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stat_df = generate_stat_results()
    odds_df = generate_odds_props(stat_df)
    stat_path = out_dir / "stat_results.parquet"
    odds_path = out_dir / "odds_props.parquet"
    stat_df.to_parquet(stat_path, index=False)
    odds_df.to_parquet(odds_path, index=False)
    logger.info("Dry-run fixtures: %d stat rows, %d odds rows", len(stat_df), len(odds_df))
    return stat_path, odds_path
