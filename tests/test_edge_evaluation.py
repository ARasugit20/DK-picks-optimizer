"""Edge Desk market-layer evaluation tests."""

from __future__ import annotations

from betting_system.markets.edge_evaluation import (
    evaluate_market_edges,
    record_market_edge_snapshot,
    record_market_resolution,
)
from betting_system.markets.base import ForecastMarket


def test_market_edge_log_pending_and_resolved_summary(tmp_path):
    """Logged market edges can be evaluated after a settlement is appended."""
    market = ForecastMarket(
        market_id="m1",
        event_id="e1",
        outcome="YES",
        market_price=0.45,
        model_prob=0.58,
        edge=0.13,
        question="Fixture market resolves yes?",
        venue="fixture",
    )
    record_market_edge_snapshot(
        [market],
        data_source="fixture_fallback",
        run_id="test-run",
        out_dir=tmp_path,
    )

    pending = evaluate_market_edges(out_dir=tmp_path)
    assert pending.logged_edges == 1
    assert pending.resolved_edges == 0
    assert pending.status == "pending_resolutions"

    record_market_resolution(
        market_id="m1",
        realized=True,
        source="test",
        out_dir=tmp_path,
    )
    resolved = evaluate_market_edges(out_dir=tmp_path)
    assert resolved.logged_edges == 1
    assert resolved.resolved_edges == 1
    assert resolved.status == "resolved"
    assert resolved.brier is not None
    assert resolved.mean_edge_realized is not None
