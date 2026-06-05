"""End-to-end pipeline smoke tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from betting_system.pipeline.run_pipeline import run_pipeline


@pytest.fixture
def pipeline_config(tmp_path: Path, repo_root: Path) -> Path:
    """Config with processed data redirected to a temp directory."""
    raw = yaml.safe_load((repo_root / "betting_system" / "config.yaml").read_text(encoding="utf-8"))
    processed = tmp_path / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    raw["data"]["processed_data_path"] = str(processed) + "/"
    raw["data"]["models_path"] = str(tmp_path / "models") + "/"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump(raw), encoding="utf-8")
    return cfg


def test_dry_run_pipeline_writes_picks_today(pipeline_config: Path):
    """--dry-run completes and writes valid picks_today.json."""
    os.environ["BETTING_CONFIG_PATH"] = str(pipeline_config)
    out = run_pipeline(dry_run=True, bankroll=500.0)
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "worthy_legs" in payload
    assert "slate_id" in payload
    assert isinstance(payload["worthy_legs"], list)
