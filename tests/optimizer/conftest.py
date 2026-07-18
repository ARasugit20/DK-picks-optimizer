"""Reusable optimizer test fixtures."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def synthetic_worthy_legs() -> list[dict[str, Any]]:
    """Small set of positive-EV legs for portfolio tests."""
    return [
        {
            "game_id": "game-a",
            "market_type": "player_points_over",
            "player_id": "player-1",
            "line": 24.5,
            "odds_american": 120,
            "p_hit": 0.62,
            "edge": 0.08,
            "ev_per_unit": 0.18,
        },
        {
            "game_id": "game-a",
            "market_type": "player_rebounds_over",
            "player_id": "player-2",
            "line": 8.5,
            "odds_american": 115,
            "p_hit": 0.61,
            "edge": 0.07,
            "ev_per_unit": 0.16,
        },
        {
            "game_id": "game-b",
            "market_type": "player_assists_over",
            "player_id": "player-3",
            "line": 6.5,
            "odds_american": 110,
            "p_hit": 0.60,
            "edge": 0.06,
            "ev_per_unit": 0.14,
        },
        {
            "game_id": "game-c",
            "market_type": "player_points_over",
            "player_id": "player-4",
            "line": 19.5,
            "odds_american": 105,
            "p_hit": 0.59,
            "edge": 0.05,
            "ev_per_unit": 0.12,
        },
        {
            "game_id": "game-d",
            "market_type": "player_points_over",
            "player_id": "player-5",
            "line": 17.5,
            "odds_american": 100,
            "p_hit": 0.58,
            "edge": 0.04,
            "ev_per_unit": 0.10,
        },
    ]
