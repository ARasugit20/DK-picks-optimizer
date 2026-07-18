"""Market trade ledger tests."""

from __future__ import annotations

import pytest

from betting_system.markets.ledger import record_trade, read_trades, settle_trade


def test_trade_ledger_records_and_settles_yes_win(tmp_path):
    """A YES trade resolves to payout minus entry cost."""
    record_trade(
        trade_id="t1",
        market_id="m1",
        side="YES",
        quantity=100,
        average_price=0.42,
        fair_value_prob=0.55,
        data_source="fixture_fallback",
        out_dir=tmp_path,
    )
    settle_trade(trade_id="t1", realized=True, out_dir=tmp_path)
    trades = read_trades(out_dir=tmp_path)

    assert len(trades) == 2
    assert trades[-1].settled
    assert trades[-1].realized_pnl == pytest.approx(58.0)


def test_trade_ledger_records_no_side_payout(tmp_path):
    """A NO trade wins when the YES outcome does not realize."""
    record_trade(
        trade_id="t2",
        market_id="m2",
        side="NO",
        quantity=50,
        average_price=0.35,
        fair_value_prob=0.40,
        data_source="fixture_fallback",
        out_dir=tmp_path,
    )
    settle_trade(trade_id="t2", realized=False, out_dir=tmp_path)
    assert read_trades(out_dir=tmp_path)[-1].realized_pnl == pytest.approx(32.5)


def test_settle_trade_rejects_unknown_id(tmp_path):
    """Unknown trade settlement fails with a clear message."""
    with pytest.raises(ValueError, match="trade_id not found"):
        settle_trade(trade_id="missing", realized=True, out_dir=tmp_path)
