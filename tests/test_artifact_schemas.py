"""Artifact schema contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from betting_system.markets.ledger import TradeRecord


def _load_schema(repo_root: Path, name: str) -> dict:
    return json.loads((repo_root / "schemas" / name).read_text(encoding="utf-8"))


def _assert_required(schema: dict, payload: dict) -> None:
    missing = set(schema.get("required", [])) - set(payload)
    assert not missing, f"missing required keys: {sorted(missing)}"


def test_market_opportunities_schema_matches_fixture_payload(repo_root: Path):
    """Market opportunities schema covers the production artifact shape."""
    schema = _load_schema(repo_root, "market_opportunities.schema.json")
    payload = {
        "meta": {"data_source": "fixture_fallback", "is_live": False, "sources": ["fixture"]},
        "data_source": "fixture_fallback",
        "hero_pick": None,
        "opportunities": [],
        "edge_summary": {"status": "pending_resolutions"},
        "portfolio": [],
        "account": {},
    }
    _assert_required(schema, payload)
    _assert_required(schema["properties"]["meta"], payload["meta"])


def test_picks_today_schema_matches_minimal_payload(repo_root: Path):
    """Picks schema documents the minimal SlatePicks artifact."""
    schema = _load_schema(repo_root, "picks_today.schema.json")
    payload = {
        "slate_id": "2026-01-01",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "bankroll": 1000.0,
        "total_exposure": 0.0,
        "parlays": [],
    }
    _assert_required(schema, payload)


def test_trade_ledger_schema_matches_record(repo_root: Path):
    """Trade ledger schema matches serialized TradeRecord rows."""
    schema = _load_schema(repo_root, "trade_ledger.schema.json")
    row = TradeRecord(
        trade_id="t1",
        market_id="m1",
        side="YES",
        quantity=10,
        average_price=0.40,
        fair_value_prob=0.55,
        data_source="fixture_fallback",
        placed_at="2026-01-01T00:00:00+00:00",
    ).to_dict()
    _assert_required(schema, row)
