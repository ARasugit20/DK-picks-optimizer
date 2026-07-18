"""Validated config loader and CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from betting_system.config import validate_config
from dk_picks.cli import app


def _write_config(tmp_path: Path, repo_root: Path, mutate=None) -> Path:  # noqa: ANN001
    raw = yaml.safe_load((repo_root / "betting_system" / "config.yaml").read_text(encoding="utf-8"))
    if mutate:
        mutate(raw)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(raw), encoding="utf-8")
    return path


def test_valid_config_passes(repo_root: Path):
    """Repository config validates successfully."""
    cfg = validate_config(repo_root / "betting_system" / "config.yaml")
    assert cfg.model["kelly_fraction"] > 0
    assert cfg.data["processed_data_path"]


def test_out_of_range_kelly_cap_fails(tmp_path: Path, repo_root: Path):
    """Kelly fraction outside configured bounds fails fast."""
    path = _write_config(
        tmp_path,
        repo_root,
        lambda raw: raw["model"].update({"kelly_fraction": 1.5}),
    )
    with pytest.raises(ValueError, match="kelly_fraction"):
        validate_config(path)


def test_missing_required_key_fails(tmp_path: Path, repo_root: Path):
    """Missing required config sections produce informative errors."""
    path = _write_config(
        tmp_path,
        repo_root,
        lambda raw: raw["model"].pop("max_slate_exposure"),
    )
    with pytest.raises(ValueError, match="max_slate_exposure"):
        validate_config(path)


def test_parlay_cap_above_slate_exposure_fails(tmp_path: Path, repo_root: Path):
    """Inconsistent exposure caps fail with a readable message."""
    path = _write_config(
        tmp_path,
        repo_root,
        lambda raw: raw["model"].update({"max_parlay_pct": 0.25, "max_slate_exposure": 0.10}),
    )
    with pytest.raises(ValueError, match="max_parlay_pct must be <= max_slate_exposure"):
        validate_config(path)


def test_validate_config_cli_success(repo_root: Path):
    """dk-picks validate-config prints config OK for the repo config."""
    result = CliRunner().invoke(
        app,
        ["validate-config", "--path", str(repo_root / "betting_system" / "config.yaml")],
    )
    assert result.exit_code == 0
    assert "config OK" in result.output


def test_validate_config_cli_failure(tmp_path: Path, repo_root: Path):
    """dk-picks validate-config exits nonzero with a useful validation message."""
    path = _write_config(
        tmp_path,
        repo_root,
        lambda raw: raw["model"].update({"max_stake_pct": 1.25}),
    )
    result = CliRunner().invoke(app, ["validate-config", "--path", str(path)])
    assert result.exit_code != 0
    assert "config invalid" in result.output
    assert "max_stake_pct" in result.output
