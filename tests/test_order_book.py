"""Order-book execution tests."""

from __future__ import annotations

import pytest

from betting_system.markets.order_book import estimate_yes_execution, normalize_order_book


def test_estimate_yes_execution_computes_slippage_and_edge():
    """Market order consumes depth and reports executable edge."""
    estimate = estimate_yes_execution(
        ask_levels=[
            {"price": 0.52, "size": 100},
            {"price": 0.55, "size": 100},
        ],
        desired_size=150,
        fair_value_prob=0.60,
    )

    assert estimate.fully_filled
    assert estimate.filled_size == 150
    assert estimate.average_price == pytest.approx(((100 * 0.52) + (50 * 0.55)) / 150)
    assert estimate.slippage == pytest.approx(estimate.average_price - 0.52)
    assert estimate.executable_edge == pytest.approx(0.60 - estimate.average_price)


def test_estimate_yes_execution_reports_partial_fill():
    """Insufficient depth leaves an explicit unfilled size."""
    estimate = estimate_yes_execution(
        ask_levels=[{"price": 0.41, "size": 25}],
        desired_size=40,
        fair_value_prob=0.50,
    )

    assert not estimate.fully_filled
    assert estimate.filled_size == 25
    assert estimate.unfilled_size == 15
    assert estimate.worst_price == 0.41


def test_order_book_validation_rejects_bad_prices():
    """Invalid prices fail before edge is computed."""
    with pytest.raises(ValueError, match="price must be in"):
        normalize_order_book([{"price": 1.25, "size": 10}])
