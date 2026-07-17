"""Polymarket Gamma API client and normalizer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger
from betting_system.markets.base import ForecastMarket


logger = get_logger(__name__)

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Politics": ("election", "president", "senate", "congress", "trump", "biden", "vote", "governor"),
    "Sports": ("nba", "nfl", "mlb", "soccer", "world cup", "fifa", "super bowl", "ufc", "tennis"),
    "Crypto": ("bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "token"),
    "Econ": ("fed", "cpi", "inflation", "rate", "gdp", "jobs", "unemployment", "s&p", "recession"),
    "Culture": ("oscar", "grammy", "movie", "album", "love island", "gta", "tv", "celebrity"),
}


def infer_category(question: str, tags: list[str] | None = None) -> str:
    """Infer market category from question text and tags."""
    text = question.lower()
    if tags:
        text += " " + " ".join(str(t).lower() for t in tags)
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return category
    return "General"


def _parse_price(raw: Any) -> float:
    """Parse Polymarket price field to 0-1 probability."""
    if raw is None:
        return 0.5
    val = float(raw)
    if val > 1.0:
        return min(max(val / 100.0, 0.01), 0.99)
    return min(max(val, 0.01), 0.99)


def normalize_polymarket_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Gamma API market row to internal schema."""
    question = str(row.get("question") or row.get("title") or row.get("description") or "Unknown market")
    tags = row.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    yes_price = _parse_price(
        row.get("outcomePrices", [None])[0]
        if isinstance(row.get("outcomePrices"), list) and row.get("outcomePrices")
        else row.get("bestBid")
        or row.get("lastTradePrice")
        or row.get("price")
    )
    if isinstance(row.get("outcomePrices"), str):
        try:
            import json

            prices = json.loads(row["outcomePrices"])
            if prices:
                yes_price = _parse_price(prices[0])
        except (json.JSONDecodeError, TypeError, IndexError):
            pass

    volume = float(row.get("volumeNum") or row.get("volume") or row.get("volume24hr") or 0)
    liquidity = float(row.get("liquidityNum") or row.get("liquidity") or 0)
    end_date = row.get("endDate") or row.get("end_date_iso")
    closes_at = None
    if end_date:
        try:
            closes_at = datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
        except ValueError:
            closes_at = None

    return {
        "market_id": f"pm-{row.get('id', row.get('conditionId', question[:20]))}",
        "event_id": str(row.get("eventId") or row.get("conditionId") or row.get("id", "")),
        "venue": "polymarket",
        "category": infer_category(question, tags if isinstance(tags, list) else None),
        "question": question,
        "outcome": "YES",
        "yes_price": yes_price,
        "volume": volume,
        "liquidity": liquidity,
        "closes_at": closes_at,
        "price_history_market": [yes_price],
        "source": "polymarket",
        "is_live": True,
        "fetched_at": datetime.now(timezone.utc),
    }


def fetch_polymarket_markets(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Fetch active markets from Polymarket Gamma API."""
    settings = load_settings()
    pm_cfg = settings.raw.get("prediction_markets", {}).get("sources", {}).get("polymarket", {})
    if not pm_cfg.get("enabled", True):
        return []

    base_url = str(pm_cfg.get("base_url", "https://gamma-api.polymarket.com"))
    limit = int(limit or pm_cfg.get("limit", 80))
    params = {
        "active": "true",
        "closed": "false",
        "limit": min(limit, 100),
        "order": pm_cfg.get("order", "volume_num"),
        "ascending": str(pm_cfg.get("ascending", False)).lower(),
    }
    url = f"{base_url.rstrip('/')}/markets"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Polymarket fetch failed: %s", exc)
        return []

    rows = data if isinstance(data, list) else data.get("markets", data.get("data", []))
    return [normalize_polymarket_row(r) for r in rows if isinstance(r, dict)]


def polymarket_rows_to_forecast(rows: list[dict[str, Any]]) -> list[ForecastMarket]:
    """Convert normalized Polymarket rows to ForecastMarket (unscored)."""
    from betting_system.markets.event_contracts import EventContractAdapter

    adapter = EventContractAdapter()
    return [adapter.to_forecast_market(r) for r in rows]
