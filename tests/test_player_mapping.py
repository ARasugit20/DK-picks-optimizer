"""Player identity mapping tests."""

from __future__ import annotations

import pandas as pd

from betting_system.pipeline.player_mapping import (
    apply_player_map,
    build_player_id_map,
    map_odds_player,
    normalize_name,
)


def test_normalize_name_strips_accents():
    """Accent normalization for international names."""
    assert normalize_name("Nikola Jokić") == normalize_name("Nikola Jokic")


def test_map_odds_player_exact_and_alias():
    """Exact and alias mapping resolve to NBA player_id."""
    catalog = pd.DataFrame(
        {
            "player_id": ["203999", "1629029"],
            "player_name": ["Nikola Jokic", "Luka Doncic"],
            "normalized": [normalize_name("Nikola Jokic"), normalize_name("Luka Doncic")],
        }
    )
    aliases = {"N. Jokic": "203999"}
    exact = map_odds_player("Nikola Jokic", catalog, aliases)
    assert exact["nba_player_id"] == "203999"
    assert exact["source"] == "exact"
    alias = map_odds_player("N. Jokic", catalog, aliases)
    assert alias["source"] == "alias"


def test_apply_player_map_filters_unmatched():
    """Unmatched odds rows are dropped after mapping."""
    odds = pd.DataFrame(
        {
            "game_id": ["g1", "g2"],
            "player_id": ["Nikola Jokic", "Unknown Player"],
            "market_type": ["player_points_over"] * 2,
            "line": [25.5, 20.5],
            "odds_american": [-110, -110],
            "implied_prob": [0.52, 0.52],
            "ingested_at": pd.to_datetime(["2024-01-01", "2024-01-01"]),
        }
    )
    stat = pd.DataFrame(
        {
            "game_id": ["g1", "g2"],
            "player_id": ["203999", "999999"],
            "player_name": ["Nikola Jokic", "Other"],
            "stat_type": ["points"] * 2,
            "actual_value": [30.0, 10.0],
            "hit": [True, False],
            "game_date": [pd.Timestamp("2024-01-01").date()] * 2,
        }
    )
    map_df = build_player_id_map(odds, stat)
    mapped = apply_player_map(odds, map_df)
    assert len(mapped) == 1
    assert mapped.iloc[0]["player_id"] == "203999"


def test_fuzzy_match_high_confidence():
    """Fuzzy matching resolves abbreviated names above threshold."""
    catalog = pd.DataFrame(
        {
            "player_id": ["1629029"],
            "player_name": ["Luka Doncic"],
            "normalized": [normalize_name("Luka Doncic")],
        }
    )
    result = map_odds_player("L Doncic", catalog, {}, fuzzy_threshold=0.5)
    assert result["nba_player_id"] == "1629029"
    assert result["source"] == "fuzzy"


def test_validate_join_rate_passes_when_aligned():
    """Join rate validation passes when odds keys exist in stat."""
    from betting_system.pipeline.player_mapping import validate_join_rate

    odds = pd.DataFrame({"game_id": ["g1"], "player_id": ["p1"]})
    stat = pd.DataFrame({"game_id": ["g1"], "player_id": ["p1"]})
    assert validate_join_rate(odds, stat, min_rate=0.5) == 1.0
