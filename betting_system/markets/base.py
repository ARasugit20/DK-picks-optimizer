"""Market-neutral forecasting abstractions for sports props and event contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class ForecastMarket:
    """One tradable forecast market (sports prop or binary event contract)."""

    market_id: str
    event_id: str
    outcome: str
    market_price: float
    model_prob: float
    edge: float
    liquidity: float | None = None
    closes_at: datetime | None = None
    venue: str = ""
    category: str = "General"
    question: str = ""
    volume: float | None = None
    open_interest: float | None = None
    price_history_market: tuple[float, ...] = field(default_factory=tuple)
    price_history_model: tuple[float, ...] = field(default_factory=tuple)
    source: str = ""
    fetched_at: datetime | None = None
    is_live: bool = False
    rationale: str = ""
    confidence: float | None = None

    @property
    def ev_per_unit(self) -> float:
        """Expected value per unit stake at market price."""
        if self.market_price <= 0 or self.market_price >= 1:
            return 0.0
        dec = 1.0 / self.market_price
        return (self.model_prob * (dec - 1.0)) - (1.0 - self.model_prob)

    @property
    def edge_pct(self) -> float:
        """Edge as percentage points."""
        return self.edge * 100.0

    @property
    def payout_multiplier(self) -> float:
        """Implied payout multiplier for YES at market price."""
        if self.market_price <= 0 or self.market_price >= 1:
            return 0.0
        return 1.0 / self.market_price

    @property
    def fair_price(self) -> float:
        """Model fair probability."""
        return self.model_prob

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON artifacts."""
        data = asdict(self)
        if self.closes_at is not None:
            data["closes_at"] = self.closes_at.isoformat()
        if self.fetched_at is not None:
            data["fetched_at"] = self.fetched_at.isoformat()
        data["ev_per_unit"] = self.ev_per_unit
        data["edge_pct"] = self.edge_pct
        data["payout_multiplier"] = self.payout_multiplier
        data["fair_price"] = self.fair_price
        data["confidence_pct"] = round((self.confidence or self.model_prob) * 100, 1)
        return data


class MarketAdapter(Protocol):
    """Protocol for converting domain-specific rows to ForecastMarket."""

    def to_forecast_market(self, row: dict) -> ForecastMarket:
        """Convert a raw row dict to ForecastMarket."""
        ...
