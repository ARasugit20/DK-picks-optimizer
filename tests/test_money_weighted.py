"""Money-weighted market metric tests."""

from __future__ import annotations

import pytest

from betting_system.markets.ledger import TradeRecord
from betting_system.markets.money_weighted import summarize_money_weighted_trades


def _trade(
    *,
    trade_id: str,
    quantity: float,
    price: float,
    fair: float,
    realized: bool,
) -> TradeRecord:
    return TradeRecord(
        trade_id=trade_id,
        market_id=trade_id,
        side="YES",
        quantity=quantity,
        average_price=price,
        fair_value_prob=fair,
        data_source="fixture_fallback",
        placed_at="2026-01-01T00:00:00+00:00",
        settled=True,
        realized=realized,
        settled_at="2026-01-02T00:00:00+00:00",
    )


def test_money_weighted_summary_uses_notional_weights():
    """Large positions dominate capital-weighted calibration."""
    trades = [
        _trade(trade_id="large", quantity=100, price=0.50, fair=0.60, realized=True),
        _trade(trade_id="small", quantity=10, price=0.20, fair=0.90, realized=False),
    ]

    summary = summarize_money_weighted_trades(trades)

    assert summary.resolved_trades == 2
    assert summary.total_notional == pytest.approx(52.0)
    assert summary.total_pnl == pytest.approx(48.0)
    assert summary.roi == pytest.approx(48.0 / 52.0)
    assert summary.money_weighted_brier == pytest.approx(((50 * 0.16) + (2 * 0.81)) / 52)
    assert summary.money_weighted_edge == pytest.approx(((50 * 0.10) + (2 * 0.70)) / 52)


def test_money_weighted_summary_handles_empty_ledger():
    """No resolved trades returns pending metrics without division by zero."""
    summary = summarize_money_weighted_trades([])
    assert summary.resolved_trades == 0
    assert summary.roi is None
    assert summary.money_weighted_brier is None
