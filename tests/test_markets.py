"""Prediction market abstraction tests."""

from __future__ import annotations

from betting_system.markets.event_contracts import EventContractAdapter
from betting_system.markets.sports_props import SportsPropAdapter


def test_sports_prop_adapter_edge():
    """Sports prop edge = model_prob - implied market price."""
    adapter = SportsPropAdapter()
    fm = adapter.to_forecast_market(
        {"game_id": "g1", "player_id": "p1", "market_type": "player_points_over",
         "odds_american": -110, "p_hit": 0.58}
    )
    assert fm.edge == fm.model_prob - fm.market_price
    assert fm.model_prob == 0.58


def test_event_contract_adapter_kalshi_price():
    """Kalshi-style YES price in cents converts to 0-1."""
    adapter = EventContractAdapter()
    fm = adapter.to_forecast_market(
        {"event_id": "e1", "contract_id": "c1", "outcome": "YES", "yes_price": 62, "model_prob": 0.70}
    )
    assert abs(fm.market_price - 0.62) < 1e-6
    assert abs(fm.edge - 0.08) < 1e-6


def test_forecast_market_ev_per_unit():
    """EV per unit uses market price and model probability."""
    from betting_system.markets.base import ForecastMarket

    fm = ForecastMarket(
        market_id="m1",
        event_id="e1",
        outcome="YES",
        market_price=0.5,
        model_prob=0.6,
        edge=0.1,
        question="Test market?",
        venue="polymarket",
        category="Politics",
    )
    assert fm.ev_per_unit > 0
    assert fm.payout_multiplier == 2.0
    assert fm.edge_pct == 10.0
    bad = ForecastMarket("m2", "e1", "YES", 0.0, 0.6, 0.6)
    assert bad.ev_per_unit == 0.0
    d = fm.to_dict()
    assert d["question"] == "Test market?"
    assert "confidence_pct" in d
