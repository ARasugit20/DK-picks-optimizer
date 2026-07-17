"""Multi-book line shopping tests."""

from __future__ import annotations

import pandas as pd

from betting_system.pipeline.line_shop import compare_books_for_leg, enrich_with_best_price, select_best_lines


def test_select_best_lines_picks_better_odds():
    """Higher American odds (+110 vs -110) selected for same leg."""
    rows = [
        {"game_id": "g1", "player_id": "p1", "market_type": "player_points_over", "line": 24.5,
         "odds_american": -110, "implied_prob": 0.52, "bookmaker": "draftkings",
         "ingested_at": pd.Timestamp("2024-01-01"), "is_closing": False},
        {"game_id": "g1", "player_id": "p1", "market_type": "player_points_over", "line": 24.5,
         "odds_american": 110, "implied_prob": 0.476, "bookmaker": "fanduel",
         "ingested_at": pd.Timestamp("2024-01-01"), "is_closing": False},
    ]
    best = compare_books_for_leg(rows)
    assert int(best["best_odds_american"]) == 110
    assert best["best_bookmaker"] == "fanduel"


def test_select_best_lines_keeps_distinct_lines():
    """Different lines remain separate legs."""
    df = pd.DataFrame([
        {"game_id": "g1", "player_id": "p1", "market_type": "player_points_over", "line": 24.5,
         "odds_american": -110, "implied_prob": 0.52, "bookmaker": "draftkings",
         "ingested_at": pd.Timestamp("2024-01-01"), "is_closing": False},
        {"game_id": "g1", "player_id": "p1", "market_type": "player_points_over", "line": 25.5,
         "odds_american": -110, "implied_prob": 0.52, "bookmaker": "fanduel",
         "ingested_at": pd.Timestamp("2024-01-01"), "is_closing": False},
    ])
    out = select_best_lines(df)
    assert len(out) == 2


def test_enrich_with_best_price_adds_model_edge():
    """Model edge vs best price is computed when model_prob provided."""
    df = pd.DataFrame([
        {"game_id": "g1", "player_id": "p1", "market_type": "player_points_over", "line": 24.5,
         "odds_american": 110, "implied_prob": 0.476, "bookmaker": "fanduel",
         "ingested_at": pd.Timestamp("2024-01-01"), "is_closing": False},
    ])
    out = enrich_with_best_price(df, model_prob=pd.Series([0.58]))
    assert "model_edge_vs_best_price" in out.columns
    assert out.iloc[0]["model_edge_vs_best_price"] > 0


def test_select_best_lines_empty():
    """Empty odds frame returns empty."""
    assert select_best_lines(pd.DataFrame()).empty
