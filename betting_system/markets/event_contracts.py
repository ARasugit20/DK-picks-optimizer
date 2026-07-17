"""Kalshi / Polymarket style binary event contract adapter."""

from __future__ import annotations

from datetime import datetime

from betting_system.markets.base import ForecastMarket


class EventContractAdapter:
    """Convert prediction-market YES contracts to ForecastMarket."""

    def to_forecast_market(self, row: dict) -> ForecastMarket:
        """Map a binary contract row to ForecastMarket.

        Args:
            row: Must include event_id, outcome, yes_price (0-1 or 0-100),
                and optionally model_prob, category, question, volume, etc.
        """
        yes_price = float(row.get("yes_price", row.get("market_price", 0.5)))
        if yes_price > 1.0:
            yes_price = yes_price / 100.0
        model_prob = float(row.get("model_prob", row.get("p_hit", yes_price)))
        edge = float(row.get("edge", model_prob - yes_price))

        hist_m = row.get("price_history_market") or []
        hist_model = row.get("price_history_model") or []
        if isinstance(hist_m, list):
            hist_m = tuple(float(x) for x in hist_m)
        else:
            hist_m = tuple(hist_m)
        if isinstance(hist_model, list):
            hist_model = tuple(float(x) for x in hist_model)
        else:
            hist_model = tuple(hist_model)

        closes = row.get("closes_at")
        if closes is not None and not isinstance(closes, datetime):
            try:
                closes = datetime.fromisoformat(str(closes).replace("Z", "+00:00"))
            except ValueError:
                closes = None

        fetched = row.get("fetched_at")
        if fetched is not None and not isinstance(fetched, datetime):
            try:
                fetched = datetime.fromisoformat(str(fetched).replace("Z", "+00:00"))
            except ValueError:
                fetched = None

        return ForecastMarket(
            market_id=str(row.get("market_id", row.get("contract_id", ""))),
            event_id=str(row.get("event_id", "")),
            outcome=str(row.get("outcome", "YES")),
            market_price=yes_price,
            model_prob=model_prob,
            edge=edge,
            liquidity=float(row["liquidity"]) if row.get("liquidity") is not None else None,
            closes_at=closes if isinstance(closes, datetime) else None,
            venue=str(row.get("venue", "")),
            category=str(row.get("category", "General")),
            question=str(row.get("question", "")),
            volume=float(row["volume"]) if row.get("volume") is not None else None,
            open_interest=float(row["open_interest"]) if row.get("open_interest") is not None else None,
            price_history_market=hist_m,
            price_history_model=hist_model,
            source=str(row.get("source", "")),
            fetched_at=fetched if isinstance(fetched, datetime) else None,
            is_live=bool(row.get("is_live", False)),
            rationale=str(row.get("rationale", "")),
            confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
        )
