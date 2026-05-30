"""Shared pytest fixtures for dk-picks-optimizer."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root directory."""
    return ROOT


@pytest.fixture
def test_config_path(tmp_path: Path, repo_root: Path) -> Path:
    """Write a copy of config.yaml with processed data pointed at a temp directory."""
    cfg_src = repo_root / "betting_system" / "config.yaml"
    raw = yaml.safe_load(cfg_src.read_text(encoding="utf-8"))
    processed = tmp_path / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    raw["data"]["processed_data_path"] = str(processed) + "/"
    out = tmp_path / "config.yaml"
    out.write_text(yaml.dump(raw), encoding="utf-8")
    return out


@pytest.fixture
def picks_today_payload() -> dict:
    """Minimal valid SlatePicks JSON for API schema tests."""
    return {
        "slate_id": "2025-01-15",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bankroll": 1000.0,
        "total_exposure": 40.0,
        "parlays": [
            {
                "parlay_id": "test-parlay-1",
                "legs": [
                    {
                        "game_id": "g1",
                        "market_type": "player_points_over",
                        "player_id": "p1",
                        "line": 24.5,
                        "odds_american": -110,
                        "p_hit": 0.58,
                        "edge": 0.04,
                        "ev_per_unit": 0.06,
                    }
                ],
                "p_parlay": 0.58,
                "ev_per_unit": 0.06,
                "stake": 20.0,
                "expected_payout": 38.18,
            }
        ],
    }


@pytest.fixture
def seeded_processed_dir(test_config_path: Path, picks_today_payload: dict) -> Path:
    """Temp processed directory with picks_today.json for API tests."""
    raw = yaml.safe_load(test_config_path.read_text(encoding="utf-8"))
    processed = Path(raw["data"]["processed_data_path"])
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "picks_today.json").write_text(
        json.dumps(picks_today_payload, default=str),
        encoding="utf-8",
    )
    return processed
