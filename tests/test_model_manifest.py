"""Model registry manifest tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.write_model_manifest import build_model_manifest, write_model_manifest


def test_build_model_manifest_includes_config_hash(repo_root: Path):
    """Manifest ties config, risk limits, and calibration metadata together."""
    manifest = build_model_manifest(config_path=repo_root / "betting_system" / "config.yaml")
    assert manifest["config_sha256"]
    assert manifest["risk_limits"]["max_slate_exposure"] > 0
    assert manifest["calibration"]["primary_method"] == "isotonic"
    assert "player_points_over" in manifest["market_types"]


def test_write_model_manifest_creates_json(tmp_path: Path, repo_root: Path):
    """Manifest writer creates a readable JSON artifact."""
    out = write_model_manifest(
        out_path=tmp_path / "artifact_manifest.json",
        config_path=repo_root / "betting_system" / "config.yaml",
        model_path=tmp_path / "missing_model.pkl",
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["model_exists"] is False
    assert payload["model_sha256"] is None
    assert payload["config_path"].endswith("config.yaml")
