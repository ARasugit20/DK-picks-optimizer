"""Kalshi Trade API client and normalizer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger
from betting_system.markets.polymarket import infer_category


logger = get_logger(__name__)


def _cents_to_prob(cents: Any) -> float:
    """Convert Kalshi cents (0-100) to 0-1 probability."""
    if cents is None:
        return 0.5
    val = float(cents)
    if val > 1.0:
        return min(max(val / 100.0, 0.01), 0.99)
    return min(max(val, 0.01), 0.99)


def normalize_kalshi_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Kalshi market row to internal schema."""
    question = str(row.get("title") or row.get("subtitle") or row.get("ticker") or "Unknown market")
    yes_price = _cents_to_prob(
        row.get("yes_ask")
        or row.get("yes_bid")
        or row.get("last_price")
        or row.get("previous_yes_ask")
    )
    volume = float(row.get("volume") or row.get("volume_24h") or 0)
    liquidity = float(row.get("open_interest") or row.get("liquidity") or 0)
    close_time = row.get("close_time") or row.get("expiration_time")
    closes_at = None
    if close_time:
        try:
            if isinstance(close_time, (int, float)):
                closes_at = datetime.fromtimestamp(float(close_time), tz=timezone.utc)
            else:
                closes_at = datetime.fromisoformat(str(close_time).replace("Z", "+00:00"))
        except (ValueError, OSError, OverflowError):
            closes_at = None

    category_hint = str(row.get("category") or row.get("series_ticker") or "")
    return {
        "market_id": f"ks-{row.get('ticker', question[:20])}",
        "event_id": str(row.get("event_ticker") or row.get("ticker") or ""),
        "venue": "kalshi",
        "category": infer_category(question, [category_hint] if category_hint else None),
        "question": question,
        "outcome": "YES",
        "yes_price": yes_price,
        "volume": volume,
        "liquidity": liquidity,
        "open_interest": liquidity,
        "closes_at": closes_at,
        "price_history_market": [yes_price],
        "source": "kalshi",
        "is_live": True,
        "fetched_at": datetime.now(timezone.utc),
    }


def fetch_kalshi_markets(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Fetch open markets from Kalshi Trade API."""
    settings = load_settings()
    ks_cfg = settings.raw.get("prediction_markets", {}).get("sources", {}).get("kalshi", {})
    if not ks_cfg.get("enabled", True):
        return []

    base_url = str(ks_cfg.get("base_url", "https://api.elections.kalshi.com/trade-api/v2"))
    limit = int(limit or ks_cfg.get("limit", 80))
    params = {
        "limit": min(limit, 200),
        "status": ks_cfg.get("status", "open"),
    }
    url = f"{base_url.rstrip('/')}/markets"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Kalshi fetch failed: %s", exc)
        return []

    markets = data.get("markets", []) if isinstance(data, dict) else data
    return [normalize_kalshi_row(r) for r in markets if isinstance(r, dict)]


def kalshi_rows_to_forecast(rows: list[dict[str, Any]]) -> list:
    """Convert normalized Kalshi rows to ForecastMarket (unscored)."""
    from betting_system.markets.event_contracts import EventContractAdapter

    adapter = EventContractAdapter()
    return [adapter.to_forecast_market(r) for r in rows]
