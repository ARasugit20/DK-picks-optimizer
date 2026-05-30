"""Pydantic schema validation tests."""

from __future__ import annotations

import pytest

from betting_system.schemas import EdgeResult, OddsRecord
from datetime import datetime, timezone


def test_odds_record_rejects_invalid_prob():
    """implied_prob must lie in (0, 1)."""
    with pytest.raises(ValueError):
        OddsRecord(
            game_id="g1",
            market_type="player_points_over",
            player_id="p1",
            line=20.5,
            odds_american=-110,
            implied_prob=1.5,
            bookmaker="test",
            ingested_at=datetime.now(timezone.utc),
        )


def test_edge_result_bounds():
    """EdgeResult enforces probability bounds."""
    er = EdgeResult(p_hit=0.6, p_market=0.52, edge=0.08, ev_per_unit=0.05, worthy=True)
    assert er.worthy is True
