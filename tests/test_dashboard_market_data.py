"""Dashboard market data loader tests."""

from __future__ import annotations

import pytest

from betting_system.dashboard.market_data import get_market_by_id, load_market_opportunities
from betting_system.pipeline.run_market_pipeline import run_market_pipeline


@pytest.fixture
def market_artifact(tmp_path, test_config_path, monkeypatch):
    """Run fixture pipeline into temp processed dir."""
    import os
    import yaml

    raw = yaml.safe_load(test_config_path.read_text(encoding="utf-8"))
    processed = tmp_path / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    raw["data"]["processed_data_path"] = str(processed) + "/"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump(raw), encoding="utf-8")
    os.environ["BETTING_CONFIG_PATH"] = str(cfg)
    run_market_pipeline(use_fixture=True)
    return processed


def test_load_market_opportunities(market_artifact):
    """Loader returns hero pick and opportunities from artifact."""
    data = load_market_opportunities(refresh_if_missing=False)
    assert data.get("hero_pick") is not None
    assert len(data.get("opportunities", [])) >= 6
    assert data.get("meta", {}).get("sources")


def test_get_market_by_id(market_artifact):
    """Lookup returns specific market dict."""
    data = load_market_opportunities(refresh_if_missing=False)
    mid = data["opportunities"][0]["market_id"]
    found = get_market_by_id(data, mid)
    assert found is not None
    assert found["market_id"] == mid
