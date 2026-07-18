"""Order-book execution model for prediction-market opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class OrderBookLevel:
    """One price level on a YES/NO order book."""

    price: float
    size: float


@dataclass(frozen=True)
class ExecutionEstimate:
    """Estimated fill quality for a market order."""

    requested_size: float
    filled_size: float
    average_price: float | None
    worst_price: float | None
    unfilled_size: float
    slippage: float | None
    executable_edge: float | None

    @property
    def fully_filled(self) -> bool:
        """Whether the order book had enough displayed depth."""
        return self.unfilled_size == 0


def normalize_order_book(levels: Iterable[dict | OrderBookLevel]) -> list[OrderBookLevel]:
    """Normalize raw order-book levels sorted from best to worst ask."""
    normalized: list[OrderBookLevel] = []
    for level in levels:
        if isinstance(level, OrderBookLevel):
            price = level.price
            size = level.size
        else:
            price = float(level["price"])
            size = float(level["size"])
        if not 0 < price < 1:
            raise ValueError("order-book price must be in (0, 1)")
        if size <= 0:
            continue
        normalized.append(OrderBookLevel(price=price, size=size))
    normalized.sort(key=lambda item: item.price)
    return normalized


def estimate_yes_execution(
    *,
    ask_levels: Iterable[dict | OrderBookLevel],
    desired_size: float,
    fair_value_prob: float,
) -> ExecutionEstimate:
    """Estimate executable YES edge after consuming displayed ask depth."""
    if desired_size <= 0:
        raise ValueError("desired_size must be positive")
    if not 0 < fair_value_prob < 1:
        raise ValueError("fair_value_prob must be in (0, 1)")

    levels = normalize_order_book(ask_levels)
    remaining = desired_size
    spent = 0.0
    filled = 0.0
    worst_price = None
    best_price = levels[0].price if levels else None

    for level in levels:
        if remaining <= 0:
            break
        take = min(remaining, level.size)
        spent += take * level.price
        filled += take
        remaining -= take
        worst_price = level.price

    avg_price = spent / filled if filled else None
    slippage = (avg_price - best_price) if avg_price is not None and best_price is not None else None
    executable_edge = (fair_value_prob - avg_price) if avg_price is not None else None
    return ExecutionEstimate(
        requested_size=float(desired_size),
        filled_size=float(filled),
        average_price=avg_price,
        worst_price=worst_price,
        unfilled_size=float(remaining),
        slippage=slippage,
        executable_edge=executable_edge,
    )
