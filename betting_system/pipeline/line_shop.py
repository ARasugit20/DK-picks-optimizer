"""Multi-book line shopping and best executable price selection."""

from __future__ import annotations

from typing import Any

import pandas as pd

from betting_system.odds_math import compute_ev_per_unit, implied_prob_from_american
from betting_system.logging_utils import get_logger


logger = get_logger(__name__)


def select_best_lines(odds_df: pd.DataFrame) -> pd.DataFrame:
    """Pick best EV line per leg across bookmakers.

    For the same prop at different books, chooses the row with highest
    expected value per unit at a reference model probability (market mid).
    When lines differ, higher line on overs / lower on unders can change EV;
    we compare using implied market probability as fair baseline.
    """
    if odds_df.empty:
        return odds_df

    df = odds_df.copy()
    if "bookmaker" not in df.columns:
        df["bookmaker"] = "unknown"

    df["market_mid_price"] = df.groupby([
        "game_id", "player_id", "market_type", "line"
    ])["implied_prob"].transform("mean")

    best_rows: list[dict[str, Any]] = []
    group_cols = ["game_id", "player_id", "market_type", "line"]
    for _, grp in df.groupby(group_cols, sort=False):
        grp = grp.copy()
        grp["ev_at_mid"] = grp.apply(
            lambda r: compute_ev_per_unit(float(r["market_mid_price"]), int(r["odds_american"])),
            axis=1,
        )
        best_idx = grp["ev_at_mid"].idxmax()
        best = grp.loc[best_idx].to_dict()
        best["best_odds_american"] = int(best["odds_american"])
        best["best_bookmaker"] = str(best["bookmaker"])
        best["best_implied_prob"] = float(implied_prob_from_american(best["best_odds_american"]))
        best_rows.append(best)

    out = pd.DataFrame(best_rows)
    logger.info("Line shop: %d unique legs from %d rows", len(out), len(df))
    return out


def enrich_with_best_price(odds_df: pd.DataFrame, model_prob: pd.Series | None = None) -> pd.DataFrame:
    """Add best-book fields and optional model edge vs best price."""
    best = select_best_lines(odds_df)
    if model_prob is not None and len(model_prob) == len(best):
        best = best.copy()
        best["model_prob"] = model_prob.values
        best["model_edge_vs_best_price"] = best["model_prob"] - best["best_implied_prob"]
    return best


def compare_books_for_leg(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return best row from a list of same-leg book offers (for tests)."""
    df = pd.DataFrame(rows)
    if "implied_prob" not in df.columns:
        df["implied_prob"] = df["odds_american"].map(implied_prob_from_american)
    return select_best_lines(df).iloc[0].to_dict()
