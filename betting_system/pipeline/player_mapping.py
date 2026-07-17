"""Map odds-feed player names to stable NBA player IDs."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger


logger = get_logger(__name__)


def normalize_name(name: str) -> str:
    """Lowercase, strip accents/punctuation for name matching."""
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_name = re.sub(r"[^a-zA-Z0-9\s]", "", ascii_name)
    return " ".join(ascii_name.lower().split())


def load_aliases(path: Path | None = None) -> dict[str, str]:
    """Load manual name -> nba_player_id overrides from YAML."""
    if path is None:
        path = Path(__file__).resolve().parents[1] / "data" / "player_aliases.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): str(v) for k, v in (raw.get("aliases") or {}).items()}


def build_player_catalog(stat_df: pd.DataFrame) -> pd.DataFrame:
    """Build lookup table from stat_results player_id and player_name."""
    if "player_name" not in stat_df.columns:
        raise ValueError("stat_df must include player_name for mapping")
    catalog = (
        stat_df[["player_id", "player_name"]]
        .drop_duplicates()
        .assign(normalized=lambda d: d["player_name"].map(normalize_name))
    )
    return catalog


def _fuzzy_ratio(a: str, b: str) -> float:
    """Simple token overlap ratio for fuzzy name match."""
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def map_odds_player(
    odds_name: str,
    catalog: pd.DataFrame,
    aliases: dict[str, str],
    *,
    fuzzy_threshold: float = 0.85,
) -> dict[str, Any]:
    """Resolve one odds player name to NBA player_id."""
    if odds_name in aliases:
        pid = aliases[odds_name]
        match = catalog[catalog["player_id"].astype(str) == pid]
        nba_name = match.iloc[0]["player_name"] if not match.empty else odds_name
        return {
            "odds_player_name": odds_name,
            "nba_player_id": pid,
            "nba_player_name": nba_name,
            "match_confidence": 1.0,
            "source": "alias",
        }

    norm = normalize_name(odds_name)
    exact = catalog[catalog["normalized"] == norm]
    if not exact.empty:
        row = exact.iloc[0]
        return {
            "odds_player_name": odds_name,
            "nba_player_id": str(row["player_id"]),
            "nba_player_name": str(row["player_name"]),
            "match_confidence": 1.0,
            "source": "exact",
        }

    best_score = 0.0
    best_row = None
    for _, row in catalog.iterrows():
        score = _fuzzy_ratio(norm, row["normalized"])
        if score > best_score:
            best_score = score
            best_row = row

    if best_row is not None and best_score >= fuzzy_threshold:
        return {
            "odds_player_name": odds_name,
            "nba_player_id": str(best_row["player_id"]),
            "nba_player_name": str(best_row["player_name"]),
            "match_confidence": float(best_score),
            "source": "fuzzy",
        }

    return {
        "odds_player_name": odds_name,
        "nba_player_id": None,
        "nba_player_name": None,
        "match_confidence": 0.0,
        "source": "unmatched",
    }


def build_player_id_map(
    odds_df: pd.DataFrame,
    stat_df: pd.DataFrame,
    *,
    out_path: Path | None = None,
) -> pd.DataFrame:
    """Map all unique odds player names to NBA IDs and persist parquet."""
    settings = load_settings()
    mapping_cfg = settings.raw.get("mapping", {})
    fuzzy_threshold = float(mapping_cfg.get("fuzzy_threshold", 0.85))
    aliases = load_aliases()
    catalog = build_player_catalog(stat_df)

    unique_names = odds_df["player_id"].astype(str).unique()
    rows = [
        map_odds_player(str(name), catalog, aliases, fuzzy_threshold=fuzzy_threshold)
        for name in unique_names
    ]
    map_df = pd.DataFrame(rows)

    out_path = out_path or Path(settings.data["processed_data_path"]) / "player_id_map.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    map_df.to_parquet(out_path, index=False)
    matched = (map_df["nba_player_id"].notna()).sum()
    logger.info("Player map: %d/%d matched", matched, len(map_df))
    return map_df


def apply_player_map(odds_df: pd.DataFrame, map_df: pd.DataFrame) -> pd.DataFrame:
    """Replace odds player_id strings with mapped NBA player_id."""
    df = odds_df.copy()
    lookup = map_df.set_index("odds_player_name")["nba_player_id"].to_dict()
    df["odds_player_name"] = df["player_id"].astype(str)
    df["player_id"] = df["odds_player_name"].map(lookup)
    before = len(df)
    df = df[df["player_id"].notna()].copy()
    df["player_id"] = df["player_id"].astype(str)
    logger.info("Odds rows after player map: %d/%d", len(df), before)
    return df


def validate_join_rate(
    odds_df: pd.DataFrame,
    stat_df: pd.DataFrame,
    *,
    min_rate: float | None = None,
) -> float:
    """Return and optionally enforce minimum odds/stat join rate."""
    settings = load_settings()
    min_rate = float(min_rate if min_rate is not None else settings.raw.get("mapping", {}).get("min_join_rate", 0.5))
    stat_keys = set(zip(stat_df["game_id"].astype(str), stat_df["player_id"].astype(str)))
    odds_keys = list(zip(odds_df["game_id"].astype(str), odds_df["player_id"].astype(str)))
    if not odds_keys:
        return 0.0
    matched = sum(1 for k in odds_keys if k in stat_keys)
    rate = matched / len(odds_keys)
    logger.info("Odds/stat join rate: %.1f%% (%d/%d)", rate * 100, matched, len(odds_keys))
    if rate < min_rate:
        raise ValueError(
            f"Odds/stat join rate {rate:.1%} below minimum {min_rate:.1%}. "
            "Check player_mapping and ingest_stats."
        )
    return rate
