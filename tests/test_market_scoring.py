"""Market scoring and curation tests."""

from __future__ import annotations

from betting_system.markets.market_curation import curate_opportunities, passes_filters
from betting_system.markets.market_fixtures import curated_market_rows
from betting_system.markets.market_scoring import score_forecast_markets
from betting_system.markets.base import ForecastMarket


def test_score_forecast_markets_produces_edge():
    """Scoring attaches model_prob and positive edge to fixture rows."""
    scored = score_forecast_markets(curated_market_rows())
    assert len(scored) > 0
    top = scored[0]
    assert top.model_prob > 0
    assert top.edge_pct != 0
    assert top.rationale


def test_curate_opportunities_diversifies():
    """Curation returns bounded feed with category diversity."""
    scored = score_forecast_markets(curated_market_rows())
    curated = curate_opportunities(scored)
    assert 1 <= len(curated) <= 8
    categories = {m.category for m in curated}
    assert len(categories) >= 2


def test_passes_filters_rejects_extreme_prices():
    """Extreme market prices are filtered out."""
    bad = ForecastMarket(
        market_id="x",
        event_id="e",
        outcome="YES",
        market_price=0.99,
        model_prob=0.99,
        edge=0.0,
        question="Test market with extreme price?",
        volume=100_000,
    )
    assert passes_filters(bad) is False
