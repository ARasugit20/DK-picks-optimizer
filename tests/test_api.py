"""FastAPI endpoint schema and status tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from betting_system.api.main import app
from betting_system.schemas import SlatePicks


@pytest.fixture
def api_client(test_config_path, seeded_processed_dir):
    """TestClient with config and picks fixture wired."""
    os.environ["BETTING_CONFIG_PATH"] = str(test_config_path)
    return TestClient(app)


def test_picks_today_returns_200_with_schema(api_client, picks_today_payload):
    """GET /picks/today returns 200 and validates against SlatePicks."""
    response = api_client.get("/picks/today")
    assert response.status_code == 200
    body = response.json()
    parsed = SlatePicks.model_validate(body)
    assert body["data_source"] == "fixture_fallback"
    assert parsed.slate_id == picks_today_payload["slate_id"]
    assert parsed.bankroll == picks_today_payload["bankroll"]
    assert len(parsed.parlays) >= 1


def test_health_endpoint_reports_artifact_flags(api_client):
    """GET /health returns service status and artifact presence."""
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "edge-desk-api"
    assert body["config_valid"] is True
    assert body["picks_today_exists"] is True


def test_model_status_endpoint_reports_model_availability(api_client):
    """GET /model/status returns model metadata without requiring an artifact."""
    response = api_client.get("/model/status")
    assert response.status_code == 200
    body = response.json()
    assert "model_available" in body
    assert "model_path" in body
    assert "metrics_available" in body


def test_picks_today_404_when_missing(test_config_path, tmp_path):
    """GET /picks/today returns 404 when no artifact exists."""
    os.environ["BETTING_CONFIG_PATH"] = str(test_config_path)
    raw_path = test_config_path.read_text(encoding="utf-8")
    import yaml

    raw = yaml.safe_load(raw_path)
    empty_dir = tmp_path / "empty_processed"
    empty_dir.mkdir()
    raw["data"]["processed_data_path"] = str(empty_dir) + "/"
    empty_cfg = tmp_path / "empty_config.yaml"
    empty_cfg.write_text(yaml.dump(raw), encoding="utf-8")
    os.environ["BETTING_CONFIG_PATH"] = str(empty_cfg)
    client = TestClient(app)
    response = client.get("/picks/today")
    assert response.status_code == 404


def test_market_opportunities_endpoint(api_client, tmp_path, test_config_path):
    """GET /markets/opportunities returns scored markets artifact."""
    from betting_system.pipeline.run_market_pipeline import run_market_pipeline

    run_market_pipeline(use_fixture=True)
    response = api_client.get("/markets/opportunities")
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "fixture_fallback"
    assert body.get("hero_pick") is not None
    assert body["hero_pick"]["data_source"] == "fixture_fallback"
    assert len(body.get("opportunities", [])) >= 1


def test_market_portfolio_endpoint(api_client):
    """GET /markets/portfolio returns positions and account."""
    response = api_client.get("/markets/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert "data_source" in body
    assert "portfolio" in body
    assert "account" in body


def test_market_edge_summary_endpoint(api_client):
    """GET /markets/edge-summary returns Edge Desk audit metrics."""
    response = api_client.get("/markets/edge-summary")
    assert response.status_code == 200
    body = response.json()
    assert "logged_edges" in body
    assert "resolved_edges" in body
    assert "status" in body


def test_market_pnl_attribution_endpoint(api_client, seeded_processed_dir):
    """GET /markets/pnl-attribution returns money-weighted trade metrics."""
    from betting_system.markets.ledger import record_trade, settle_trade

    record_trade(
        trade_id="api-trade-1",
        market_id="api-market-1",
        side="YES",
        quantity=100,
        average_price=0.40,
        fair_value_prob=0.55,
        data_source="fixture_fallback",
        out_dir=seeded_processed_dir,
    )
    settle_trade(trade_id="api-trade-1", realized=True, out_dir=seeded_processed_dir)

    response = api_client.get("/markets/pnl-attribution")
    assert response.status_code == 200
    body = response.json()
    assert body["trade_count"] == 2
    assert body["money_weighted"]["resolved_trades"] == 1
    assert body["money_weighted"]["total_pnl"] == 60.0
