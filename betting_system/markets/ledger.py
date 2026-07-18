"""Trade ledger for converting event probabilities into auditable PnL."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from betting_system.config import load_settings

Side = Literal["YES", "NO"]


def _processed_dir() -> Path:
    return Path(load_settings().data["processed_data_path"])


def ledger_path(out_dir: Path | None = None) -> Path:
    """Return the durable trade ledger path."""
    return (out_dir or _processed_dir()) / "market_trade_ledger.jsonl"


@dataclass(frozen=True)
class TradeRecord:
    """One auditable paper/live market trade record."""

    trade_id: str
    market_id: str
    side: Side
    quantity: float
    average_price: float
    fair_value_prob: float
    data_source: str
    placed_at: str
    settled: bool = False
    realized: bool | None = None
    settled_at: str | None = None

    @property
    def notional(self) -> float:
        """Capital spent to enter the position."""
        return self.quantity * self.average_price

    @property
    def max_payout(self) -> float:
        """Maximum contract payout before fees."""
        return self.quantity

    @property
    def realized_pnl(self) -> float | None:
        """Resolved PnL for a fully settled binary contract."""
        if not self.settled or self.realized is None:
            return None
        yes_won = bool(self.realized)
        side_won = yes_won if self.side == "YES" else not yes_won
        payout = self.max_payout if side_won else 0.0
        return payout - self.notional

    def to_dict(self) -> dict[str, Any]:
        """Serialize the trade record."""
        data = asdict(self)
        data["notional"] = self.notional
        data["max_payout"] = self.max_payout
        data["realized_pnl"] = self.realized_pnl
        return data


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, default=str) + "\n")


def append_trade(record: TradeRecord, *, out_dir: Path | None = None) -> Path:
    """Append a trade record to the durable ledger."""
    path = ledger_path(out_dir)
    _append_jsonl(path, record.to_dict())
    return path


def record_trade(
    *,
    trade_id: str,
    market_id: str,
    side: Side,
    quantity: float,
    average_price: float,
    fair_value_prob: float,
    data_source: str,
    out_dir: Path | None = None,
) -> Path:
    """Create and append an unsettled trade record."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if not 0 < average_price < 1:
        raise ValueError("average_price must be in (0, 1)")
    if not 0 < fair_value_prob < 1:
        raise ValueError("fair_value_prob must be in (0, 1)")
    return append_trade(
        TradeRecord(
            trade_id=trade_id,
            market_id=market_id,
            side=side,
            quantity=quantity,
            average_price=average_price,
            fair_value_prob=fair_value_prob,
            data_source=data_source,
            placed_at=datetime.now(timezone.utc).isoformat(),
        ),
        out_dir=out_dir,
    )


def read_trades(*, out_dir: Path | None = None) -> list[TradeRecord]:
    """Read all trade records from the ledger."""
    path = ledger_path(out_dir)
    if not path.exists():
        return []
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [
        TradeRecord(
            trade_id=str(row["trade_id"]),
            market_id=str(row["market_id"]),
            side=row["side"],
            quantity=float(row["quantity"]),
            average_price=float(row["average_price"]),
            fair_value_prob=float(row["fair_value_prob"]),
            data_source=str(row["data_source"]),
            placed_at=str(row["placed_at"]),
            settled=bool(row.get("settled", False)),
            realized=row.get("realized"),
            settled_at=row.get("settled_at"),
        )
        for row in rows
    ]


def settle_trade(
    *,
    trade_id: str,
    realized: bool,
    out_dir: Path | None = None,
) -> Path:
    """Append a settled copy of the latest matching trade record."""
    trades = [trade for trade in read_trades(out_dir=out_dir) if trade.trade_id == trade_id]
    if not trades:
        raise ValueError(f"trade_id not found: {trade_id}")
    latest = trades[-1]
    return append_trade(
        TradeRecord(
            trade_id=latest.trade_id,
            market_id=latest.market_id,
            side=latest.side,
            quantity=latest.quantity,
            average_price=latest.average_price,
            fair_value_prob=latest.fair_value_prob,
            data_source=latest.data_source,
            placed_at=latest.placed_at,
            settled=True,
            realized=realized,
            settled_at=datetime.now(timezone.utc).isoformat(),
        ),
        out_dir=out_dir,
    )
