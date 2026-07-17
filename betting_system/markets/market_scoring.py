"""Fair-value scoring for prediction-market contracts."""

from __future__ import annotations

import math
from typing import Any

from betting_system.config import load_settings
from betting_system.markets.base import ForecastMarket


CATEGORY_PRIORS: dict[str, float] = {
    "Politics": 0.02,
    "Sports": 0.03,
    "Crypto": 0.04,
    "Econ": 0.025,
    "Culture": 0.02,
    "General": 0.01,
}


def _scoring_cfg() -> dict[str, Any]:
    return load_settings().raw.get("prediction_markets", {}).get("scoring", {})


def _momentum_signal(history: tuple[float, ...]) -> float:
    """Estimate short-term momentum from price history."""
    if len(history) < 2:
        return 0.0
    return history[-1] - history[0]


def _liquidity_signal(volume: float | None, liquidity: float | None) -> float:
    """Higher liquidity/volume -> slightly more confidence in market efficiency."""
    vol = volume or 0
    liq = liquidity or 0
    if vol <= 0 and liq <= 0:
        return 0.0
    score = math.log10(max(vol, liq, 1.0))
    return min(score / 8.0, 0.05)


def score_market_row(row: dict[str, Any]) -> dict[str, Any]:
    """Score a normalized market row and attach model_prob, edge, rationale."""
    cfg = _scoring_cfg()
    market_price = float(row.get("yes_price", row.get("market_price", 0.5)))
    if market_price > 1.0:
        market_price /= 100.0
    market_price = min(max(market_price, 0.01), 0.99)

    history = tuple(row.get("price_history_market") or [market_price])
    if len(history) == 1:
        # Synthetic 7-day history for chart when only spot price available
        delta = market_price * 0.08
        history = tuple(
            max(0.01, min(0.99, market_price - delta + (delta * i / 6)))
            for i in range(7)
        )
        row = {**row, "price_history_market": list(history)}

    momentum_w = float(cfg.get("momentum_weight", 0.35))
    liq_w = float(cfg.get("liquidity_weight", 0.25))
    prior_w = float(cfg.get("category_prior_weight", 0.15))
    category = str(row.get("category", "General"))
    prior = CATEGORY_PRIORS.get(category, 0.01)

    momentum = _momentum_signal(history)
    liq_sig = _liquidity_signal(row.get("volume"), row.get("liquidity"))
    edge_signal = momentum_w * momentum + prior_w * prior - liq_w * liq_sig * 0.5
    model_prob = min(max(market_price + edge_signal, 0.02), 0.98)
    edge = model_prob - market_price
    confidence = min(max(abs(edge) + market_price * 0.1 + (row.get("volume", 0) > 1e6) * 0.05, 0.5), 0.95)

    rationale_parts = [
        f"Market at {market_price:.0%}",
        f"momentum signal {momentum:+.1%}",
        f"category prior {category}",
    ]
    if row.get("volume"):
        rationale_parts.append(f"volume ${float(row['volume']):,.0f}")

    row["model_prob"] = model_prob
    row["market_price"] = market_price
    row["yes_price"] = market_price
    row["edge"] = edge
    row["confidence"] = confidence
    row["price_history_model"] = [
        min(max(h + edge * (i + 1) / len(history), 0.02), 0.98) for i, h in enumerate(history)
    ]
    row["rationale"] = "; ".join(rationale_parts) + "."
    return row


def score_forecast_markets(rows: list[dict[str, Any]]) -> list[ForecastMarket]:
    """Score normalized rows and return ForecastMarket list."""
    from betting_system.markets.event_contracts import EventContractAdapter

    cfg = _scoring_cfg()
    min_edge = float(cfg.get("min_edge_pct", 2.0)) / 100.0
    adapter = EventContractAdapter()
    scored: list[ForecastMarket] = []
    for raw in rows:
        row = score_market_row(dict(raw))
        fm = adapter.to_forecast_market(row)
        if fm.edge >= min_edge or row.get("source") == "fixture":
            scored.append(fm)
    return scored
