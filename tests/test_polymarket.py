"""Polymarket client tests."""

from __future__ import annotations

from betting_system.markets.polymarket import infer_category, normalize_polymarket_row


def test_infer_category_politics():
    """Politics keywords map to Politics category."""
    assert infer_category("Will Trump win the 2028 election?") == "Politics"


def test_infer_category_crypto():
    """Crypto keywords map to Crypto category."""
    assert infer_category("Will Bitcoin exceed $150k?") == "Crypto"


def test_normalize_polymarket_row():
    """Gamma API row normalizes to internal schema."""
    row = normalize_polymarket_row(
        {
            "id": "123",
            "question": "Fed cuts rates in July?",
            "outcomePrices": "[\"0.54\", \"0.46\"]",
            "volumeNum": 2400000,
            "liquidityNum": 180000,
        }
    )
    assert row["venue"] == "polymarket"
    assert row["category"] == "Econ"
    assert abs(row["yes_price"] - 0.54) < 0.01
    assert row["volume"] == 2_400_000
