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
    assert parsed.slate_id == picks_today_payload["slate_id"]
    assert parsed.bankroll == picks_today_payload["bankroll"]
    assert len(parsed.parlays) >= 1


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
