"""Money-weighted calibration and return metrics for market trades."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from betting_system.markets.ledger import TradeRecord


@dataclass(frozen=True)
class MoneyWeightedSummary:
    """Capital-weighted performance summary."""

    resolved_trades: int
    total_notional: float
    total_pnl: float
    roi: float | None
    money_weighted_brier: float | None
    money_weighted_edge: float | None

    def to_dict(self) -> dict[str, float | int | None]:
        """Serialize summary for API payloads."""
        return {
            "resolved_trades": self.resolved_trades,
            "total_notional": self.total_notional,
            "total_pnl": self.total_pnl,
            "roi": self.roi,
            "money_weighted_brier": self.money_weighted_brier,
            "money_weighted_edge": self.money_weighted_edge,
        }


def summarize_money_weighted_trades(trades: Iterable[TradeRecord]) -> MoneyWeightedSummary:
    """Summarize resolved trades with notional as the weight."""
    resolved = [trade for trade in trades if trade.settled and trade.realized is not None]
    if not resolved:
        return MoneyWeightedSummary(
            resolved_trades=0,
            total_notional=0.0,
            total_pnl=0.0,
            roi=None,
            money_weighted_brier=None,
            money_weighted_edge=None,
        )

    notionals = [trade.notional for trade in resolved]
    total_notional = sum(notionals)
    total_pnl = sum(float(trade.realized_pnl or 0.0) for trade in resolved)
    if total_notional <= 0:
        return MoneyWeightedSummary(
            resolved_trades=len(resolved),
            total_notional=0.0,
            total_pnl=total_pnl,
            roi=None,
            money_weighted_brier=None,
            money_weighted_edge=None,
        )

    weighted_brier = 0.0
    weighted_edge = 0.0
    for trade, weight in zip(resolved, notionals, strict=True):
        outcome = 1.0 if bool(trade.realized) else 0.0
        prob = trade.fair_value_prob if trade.side == "YES" else 1.0 - trade.fair_value_prob
        price = trade.average_price
        weighted_brier += weight * ((prob - outcome) ** 2)
        weighted_edge += weight * (prob - price)

    return MoneyWeightedSummary(
        resolved_trades=len(resolved),
        total_notional=total_notional,
        total_pnl=total_pnl,
        roi=total_pnl / total_notional,
        money_weighted_brier=weighted_brier / total_notional,
        money_weighted_edge=weighted_edge / total_notional,
    )
