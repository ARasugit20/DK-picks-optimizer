"""Kalshi client tests."""

from __future__ import annotations

from betting_system.markets.kalshi import normalize_kalshi_row


def test_normalize_kalshi_row_cents():
    """Kalshi cents convert to 0-1 probability."""
    row = normalize_kalshi_row(
        {
            "ticker": "PRES-28-R",
            "title": "Republican wins 2028 presidential election?",
            "yes_ask": 49,
            "volume": 14_200_000,
            "open_interest": 950_000,
            "category": "Politics",
        }
    )
    assert row["venue"] == "kalshi"
    assert abs(row["yes_price"] - 0.49) < 0.01
    assert row["category"] == "Politics"
