"""Dashboard data loader for prediction-market terminal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from betting_system.config import load_settings
from betting_system.pipeline.run_market_pipeline import run_market_pipeline


def processed_dir() -> Path:
    """Return processed data directory."""
    return Path(load_settings().data["processed_data_path"])


def load_market_opportunities(*, refresh_if_missing: bool = True) -> dict[str, Any]:
    """Load market opportunities artifact, optionally running pipeline if absent."""
    path = processed_dir() / "market_opportunities.json"
    if not path.exists() and refresh_if_missing:
        run_market_pipeline(use_fixture=True)
    if not path.exists():
        return {
            "meta": {"is_live": False, "data_source": "fixture_fallback", "fallback_reason": "no data"},
            "data_source": "fixture_fallback",
            "hero_pick": None,
            "opportunities": [],
            "edge_summary": {"logged_edges": 0, "resolved_edges": 0, "status": "no_edge_log"},
            "portfolio": [],
            "account": {"equity": 0, "daily_edge_captured": 0, "open_pnl": 0},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def get_market_by_id(data: dict[str, Any], market_id: str) -> dict[str, Any] | None:
    """Find a market dict by id from loaded opportunities."""
    for m in data.get("opportunities", []):
        if m.get("market_id") == market_id:
            return m
    hero = data.get("hero_pick")
    if hero and hero.get("market_id") == market_id:
        return hero
    return None
