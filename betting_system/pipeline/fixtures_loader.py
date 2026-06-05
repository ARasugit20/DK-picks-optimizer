"""Dry-run fixture materialization for the end-to-end pipeline."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from betting_system.logging_utils import get_logger


logger = get_logger(__name__)

PLAYERS = [
    ("p1", "D. Lillard", "home"),
    ("p2", "N. Jokic", "home"),
    ("p3", "T. Herro", "home"),
    ("p4", "J. Tatum", "away"),
    ("p5", "J. Brunson", "home"),
    ("p6", "D. Fox", "away"),
    ("p7", "S. Gilgeous-Alexander", "home"),
    ("p8", "A. Edwards", "away"),
]


def _rng(seed: int) -> np.random.Generator:
    """Return a deterministic RNG for fixture generation."""
    return np.random.default_rng(seed)


def generate_stat_results(*, n_games: int = 80, seed: int = 42) -> pd.DataFrame:
    """Build synthetic stat results with home_away and game dates."""
    rng = _rng(seed)
    rows: list[dict] = []
    base = date(2024, 10, 1)
    for game_idx in range(n_games):
        game_date = base + timedelta(days=game_idx * 2)
        game_id = f"g_{game_date.isoformat()}"
        for player_id, _name, home_away in PLAYERS:
            actual = float(rng.integers(8, 35))
            line = actual + rng.integers(-4, 5)
            hit = actual > line
            rows.append(
                {
                    "game_id": game_id,
                    "player_id": player_id,
                    "stat_type": "points",
                    "actual_value": actual,
                    "hit": hit,
                    "game_date": game_date,
                    "home_away": home_away,
                }
            )
    return pd.DataFrame(rows)


def generate_odds_props(stat_df: pd.DataFrame, *, seed: int = 42) -> pd.DataFrame:
    """Build odds rows aligned to stat results for dry-run ingest."""
    rng = _rng(seed)
    rows: list[dict] = []
    for _, row in stat_df.iterrows():
        line = float(row["actual_value"]) + rng.integers(-3, 4)
        odds_am = int(rng.choice([-125, -115, -110, -105, 100, 110]))
        implied = 100 / (100 + abs(odds_am)) if odds_am < 0 else 100 / (odds_am + 100)
        rows.append(
            {
                "game_id": row["game_id"],
                "player_id": row["player_id"],
                "market_type": "player_points_over",
                "line": line,
                "odds_american": odds_am,
                "implied_prob": float(implied),
                "bookmaker": "demo",
                "ingested_at": pd.Timestamp(f"{row['game_date']}T12:00:00Z"),
                "is_closing": False,
            }
        )
    return pd.DataFrame(rows)


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
