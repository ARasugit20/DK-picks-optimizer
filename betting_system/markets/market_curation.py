"""Market curation: filter, rank, and diversify prediction-market opportunities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from betting_system.config import load_settings
from betting_system.markets.base import ForecastMarket


def _curation_cfg() -> dict[str, Any]:
    return load_settings().raw.get("prediction_markets", {}).get("curation", {})


def passes_filters(market: ForecastMarket) -> bool:
    """Return True if market meets minimum curation thresholds."""
    cfg = _curation_cfg()
    min_vol = float(cfg.get("min_volume_usd", 0))
    min_q = int(cfg.get("min_question_length", 10))
    if len(market.question) < min_q:
        return False
    if market.volume is not None and market.volume < min_vol and market.source != "fixture":
        return False
    if market.market_price <= 0.02 or market.market_price >= 0.98:
        return False
    if market.closes_at is not None:
        days = (market.closes_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
        max_days = int(cfg.get("max_days_to_close", 365))
        if days < 0 or days > max_days:
            return False
    return True


def rank_markets(markets: list[ForecastMarket], *, sort_by: str = "edge") -> list[ForecastMarket]:
    """Rank markets by edge, confidence, or volume."""
    if sort_by == "confidence":
        return sorted(markets, key=lambda m: m.confidence or m.model_prob, reverse=True)
    if sort_by == "volume":
        return sorted(markets, key=lambda m: m.volume or 0, reverse=True)
    return sorted(markets, key=lambda m: m.edge, reverse=True)


def diversify_by_category(markets: list[ForecastMarket]) -> list[ForecastMarket]:
    """Select top markets with per-category caps for feed diversity."""
    cfg = _curation_cfg()
    max_total = int(cfg.get("max_opportunities", 8))
    max_per_cat = int(cfg.get("max_per_category", 2))
    selected: list[ForecastMarket] = []
    cat_counts: dict[str, int] = {}
    for m in markets:
        cat = m.category or "General"
        if cat_counts.get(cat, 0) >= max_per_cat:
            continue
        selected.append(m)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        if len(selected) >= max_total:
            break
    return selected


def curate_opportunities(
    markets: list[ForecastMarket],
    *,
    sort_by: str = "edge",
    category: str | None = None,
) -> list[ForecastMarket]:
    """Filter, optionally category-slice, rank, and diversify markets."""
    filtered = [m for m in markets if passes_filters(m)]
    if category and category.lower() not in ("all", ""):
        filtered = [m for m in filtered if m.category.lower() == category.lower()]
    ranked = rank_markets(filtered, sort_by=sort_by)
    return diversify_by_category(ranked)
