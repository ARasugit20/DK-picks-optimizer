"""Market pipeline integration tests."""

from __future__ import annotations

import json
import os

import pytest
import yaml

from betting_system.pipeline.run_market_pipeline import (
    build_opportunities,
    ingest_market_rows,
    run_market_pipeline,
    write_market_artifacts,
)


@pytest.fixture
def market_cfg(tmp_path, repo_root):
    raw = yaml.safe_load((repo_root / "betting_system" / "config.yaml").read_text(encoding="utf-8"))
    processed = tmp_path / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    raw["data"]["processed_data_path"] = str(processed) + "/"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump(raw), encoding="utf-8")
    os.environ["BETTING_CONFIG_PATH"] = str(cfg)
    return cfg, processed


def test_run_market_pipeline_fixture_writes_artifact(market_cfg):
    """Fixture pipeline writes market_opportunities.json."""
    _, processed = market_cfg
    out = run_market_pipeline(use_fixture=True)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["data_source"] == "fixture_fallback"
    assert data["meta"]["data_source"] == "fixture_fallback"
    assert data["hero_pick"] is not None
    assert data["hero_pick"]["data_source"] == "fixture_fallback"
    assert data["edge_summary"]["logged_edges"] >= 1
    assert len(data["opportunities"]) >= 6
    assert (processed / "prediction_markets.parquet").exists()
    assert (processed / "market_edge_log.jsonl").exists()


def test_ingest_market_rows_live_fallback(monkeypatch, market_cfg):
    """When live APIs return empty, fixture fallback is used."""
    monkeypatch.setattr(
        "betting_system.pipeline.run_market_pipeline.fetch_polymarket_markets",
        lambda **_: [],
    )
    monkeypatch.setattr(
        "betting_system.pipeline.run_market_pipeline.fetch_kalshi_markets",
        lambda **_: [],
    )
    rows, meta = ingest_market_rows(use_fixture=False)
    assert len(rows) >= 6
    assert meta.get("fallback_reason")


def test_build_and_write_opportunities(market_cfg):
    """Scoring and artifact writer produce valid JSON payload."""
    _, processed = market_cfg
    rows, meta = ingest_market_rows(use_fixture=True)
    opps = build_opportunities(rows)
    path = write_market_artifacts(opps, meta)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["account"]["equity"] > 0
    assert payload["portfolio"]
