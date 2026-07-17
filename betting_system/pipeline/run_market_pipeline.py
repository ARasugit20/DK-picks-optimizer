"""Prediction-market pipeline: ingest, score, curate, write artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger
from betting_system.markets.base import ForecastMarket
from betting_system.markets.kalshi import fetch_kalshi_markets
from betting_system.markets.market_curation import curate_opportunities
from betting_system.markets.market_fixtures import curated_market_rows
from betting_system.markets.market_scoring import score_forecast_markets
from betting_system.markets.polymarket import fetch_polymarket_markets


logger = get_logger(__name__)


DEFAULT_PORTFOLIO = [
    {
        "market_id": "fix-fed-july-cut",
        "question": "Fed cuts rates at July 2026 FOMC meeting?",
        "side": "YES",
        "qty": 250,
        "avg_price": 0.51,
        "mark_price": 0.54,
        "pnl": 7.5,
        "venue": "polymarket",
    },
    {
        "market_id": "fix-btc-150k",
        "question": "BTC above $150,000 on Dec 31, 2026?",
        "side": "YES",
        "qty": 120,
        "avg_price": 0.28,
        "mark_price": 0.31,
        "pnl": 3.6,
        "venue": "polymarket",
    },
    {
        "market_id": "fix-gta-vi",
        "question": "GTA VI releases before Jan 1, 2027?",
        "side": "YES",
        "qty": 80,
        "avg_price": 0.58,
        "mark_price": 0.62,
        "pnl": 3.2,
        "venue": "polymarket",
    },
]


def ingest_market_rows(*, use_fixture: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch live markets or return curated fixtures with metadata."""
    meta: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_live": False,
        "sources": [],
        "fallback_reason": None,
    }
    if use_fixture:
        meta["sources"] = ["fixture"]
        meta["fallback_reason"] = "fixture mode requested"
        return curated_market_rows(), meta

    pm_rows = fetch_polymarket_markets()
    ks_rows = fetch_kalshi_markets()
    rows = pm_rows + ks_rows
    meta["sources"] = []
    if pm_rows:
        meta["sources"].append("polymarket")
    if ks_rows:
        meta["sources"].append("kalshi")

    if rows:
        meta["is_live"] = True
        return rows, meta

    settings = load_settings()
    if settings.raw.get("prediction_markets", {}).get("fixture_fallback", True):
        meta["fallback_reason"] = "live APIs unavailable; using curated fixtures"
        meta["sources"] = ["fixture"]
        return curated_market_rows(), meta

    return [], meta


def build_opportunities(
    rows: list[dict[str, Any]],
    *,
    sort_by: str = "edge",
    category: str | None = None,
) -> list[ForecastMarket]:
    """Score and curate market rows into ranked opportunities."""
    scored = score_forecast_markets(rows)
    return curate_opportunities(scored, sort_by=sort_by, category=category)


def write_market_artifacts(
    opportunities: list[ForecastMarket],
    meta: dict[str, Any],
    *,
    out_dir: Path | None = None,
) -> Path:
    """Write market_opportunities.json and prediction_markets.parquet."""
    settings = load_settings()
    out_dir = out_dir or Path(settings.data["processed_data_path"])
    out_dir.mkdir(parents=True, exist_ok=True)

    ui_cfg = settings.raw.get("prediction_markets", {}).get("ui", {})
    hero = opportunities[0] if opportunities else None
    payload = {
        "meta": meta,
        "hero_pick": hero.to_dict() if hero else None,
        "opportunities": [m.to_dict() for m in opportunities],
        "portfolio": DEFAULT_PORTFOLIO,
        "account": {
            "equity": float(ui_cfg.get("starting_equity", 24847.32)),
            "daily_edge_captured": float(ui_cfg.get("daily_edge_captured", 342.18)),
            "open_pnl": sum(p["pnl"] for p in DEFAULT_PORTFOLIO),
        },
    }
    json_path = out_dir / "market_opportunities.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    if opportunities:
        df = pd.DataFrame([m.to_dict() for m in opportunities])
        df.to_parquet(out_dir / "prediction_markets.parquet", index=False)

    logger.info("Wrote market opportunities -> %s (%d markets)", json_path, len(opportunities))
    return json_path


def run_market_pipeline(*, use_fixture: bool = False) -> Path:
    """Run full prediction-market pipeline."""
    rows, meta = ingest_market_rows(use_fixture=use_fixture)
    opportunities = build_opportunities(rows)
    return write_market_artifacts(opportunities, meta)


def main() -> None:
    """CLI entrypoint for dk-market-pipeline."""
    parser = argparse.ArgumentParser(description="Run prediction-market ingestion and scoring")
    parser.add_argument("--fixture", action="store_true", help="Use curated fixtures instead of live APIs")
    args = parser.parse_args()
    out = run_market_pipeline(use_fixture=args.fixture)
    logger.info("Market pipeline complete -> %s", out)


if __name__ == "__main__":
    main()
