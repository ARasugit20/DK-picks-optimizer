"""Sports prop market adapter."""

from __future__ import annotations

from datetime import datetime

from betting_system.markets.base import ForecastMarket
from betting_system.odds_math import implied_prob_from_american


class SportsPropAdapter:
    """Convert sportsbook prop legs to ForecastMarket."""

    def to_forecast_market(self, row: dict) -> ForecastMarket:
        """Map a worthy leg dict to ForecastMarket."""
        odds = int(row["odds_american"])
        market_price = implied_prob_from_american(odds)
        model_prob = float(row.get("p_hit", row.get("model_prob", 0.5)))
        return ForecastMarket(
            market_id=str(row.get("market_type", "")),
            event_id=str(row.get("game_id", "")),
            outcome=str(row.get("player_id", "")),
            market_price=market_price,
            model_prob=model_prob,
            edge=model_prob - market_price,
            liquidity=None,
            closes_at=row.get("closes_at") if isinstance(row.get("closes_at"), datetime) else None,
        )
