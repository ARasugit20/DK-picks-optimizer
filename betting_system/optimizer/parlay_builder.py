from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import pandas as pd

from betting_system.config import load_settings
from betting_system.odds_math import american_to_decimal


def load_correlation_matrix(path: str | Path) -> pd.DataFrame:
    """Load a pairwise leg correlation matrix from parquet or CSV."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
    return df


def _pair_key(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, str, str, str]:
    """Build a stable key for two legs (unused in v1 ranking)."""
    return (a["market_type"], a["player_id"], b["market_type"], b["player_id"])


def _corr_lookup(corr_df: pd.DataFrame, leg_a: dict[str, Any], leg_b: dict[str, Any], default: float) -> float:
    """Return pairwise correlation for two legs, or *default* when unknown."""
    if corr_df.empty:
        return default
    # Expected columns: market_type_a, player_id_a, market_type_b, player_id_b, corr
    cols = {"market_type_a", "player_id_a", "market_type_b", "player_id_b", "corr"}
    if not cols.issubset(set(corr_df.columns)):
        return default
    a = (leg_a["market_type"], str(leg_a["player_id"]))
    b = (leg_b["market_type"], str(leg_b["player_id"]))
    mask = (
        (corr_df["market_type_a"] == a[0])
        & (corr_df["player_id_a"].astype(str) == a[1])
        & (corr_df["market_type_b"] == b[0])
        & (corr_df["player_id_b"].astype(str) == b[1])
    )
    if mask.any():
        return float(corr_df.loc[mask, "corr"].iloc[0])
    # symmetric
    mask = (
        (corr_df["market_type_a"] == b[0])
        & (corr_df["player_id_a"].astype(str) == b[1])
        & (corr_df["market_type_b"] == a[0])
        & (corr_df["player_id_b"].astype(str) == a[1])
    )
    if mask.any():
        return float(corr_df.loc[mask, "corr"].iloc[0])
    return default


def build_parlay_candidates(
    worthy_legs: list[dict[str, Any]],
    *,
    corr_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Build ranked correlated multi-leg portfolio candidates from worthy legs."""
    settings = load_settings()
    cfg = settings.model
    max_legs = int(cfg["max_legs_per_parlay"])
    corr_max_pair = float(cfg["correlation_max_pair"])
    corr_default = float(cfg.get("correlation_default_pair", 0.0))

    corr_df = load_correlation_matrix(corr_path) if corr_path else pd.DataFrame()

    # Generate combinations 2..max_legs (parlays of size 1 belong in singles path)
    candidates: list[dict[str, Any]] = []
    for n in range(2, max_legs + 1):
        for combo in itertools.combinations(worthy_legs, n):
            # Filter: no two legs from same player
            players = [c["player_id"] for c in combo]
            if len(set(players)) != len(players):
                continue

            # Filter: correlation threshold (pairwise)
            ok = True
            discount = 1.0
            for i in range(len(combo)):
                for j in range(i + 1, len(combo)):
                    corr = _corr_lookup(corr_df, combo[i], combo[j], default=corr_default)
                    if abs(corr) > corr_max_pair:
                        ok = False
                        break
                    # conservative multiplicative discount
                    discount *= max(0.0, 1.0 - abs(corr))
                if not ok:
                    break
            if not ok:
                continue

            p_parlay = 1.0
            dec_parlay = 1.0
            for leg in combo:
                p_parlay *= float(leg["p_hit"])
                dec_parlay *= american_to_decimal(int(leg["odds_american"]))
            p_parlay *= discount

            # EV per unit stake for parlay
            parlay_ev = (p_parlay * (dec_parlay - 1.0)) - (1.0 - p_parlay)
            candidates.append(
                {
                    "legs": list(combo),
                    "p_parlay": float(p_parlay),
                    "decimal_odds": float(dec_parlay),
                    "ev_per_unit": float(parlay_ev),
                    "corr_discount": float(discount),
                }
            )
    # rank by EV
    candidates.sort(key=lambda x: x["ev_per_unit"], reverse=True)
    return candidates

