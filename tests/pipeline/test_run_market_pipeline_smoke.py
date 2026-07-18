"""Offline smoke tests for the prediction-market pipeline."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest
import yaml

from betting_system.pipeline.run_market_pipeline import run_market_pipeline
from scripts.generate_synthetic_slate import generate_synthetic_slate


@pytest.fixture
def isolated_market_config(tmp_path: Path, repo_root: Path) -> tuple[Path, Path]:
    """Point processed artifacts at a temporary directory."""
    raw = yaml.safe_load((repo_root / "betting_system" / "config.yaml").read_text(encoding="utf-8"))
    processed = tmp_path / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    raw["data"]["processed_data_path"] = str(processed) + "/"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump(raw), encoding="utf-8")
    os.environ["BETTING_CONFIG_PATH"] = str(cfg)
    return cfg, processed


def test_generate_synthetic_slate_writes_expected_schema(tmp_path: Path):
    """Synthetic slate generator writes the documented deterministic schema."""
    out = generate_synthetic_slate(out_path=tmp_path / "prediction_markets.parquet", seed=7)
    df = pd.read_parquet(out)
    assert list(df.columns) == [
        "market_id",
        "question",
        "mark_price",
        "model_p_hit",
        "venue",
        "close_date",
    ]
    assert pd.api.types.is_float_dtype(df["mark_price"])
    assert pd.api.types.is_float_dtype(df["model_p_hit"])
    assert df["market_id"].is_unique


def test_run_market_pipeline_fixture_smoke_no_network(monkeypatch, isolated_market_config):
    """Fixture mode writes JSON/parquet artifacts without touching network clients."""
    _, processed = isolated_market_config

    def fail_network(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("fixture smoke test must not call live network clients")

    monkeypatch.setattr("betting_system.pipeline.run_market_pipeline.fetch_polymarket_markets", fail_network)
    monkeypatch.setattr("betting_system.pipeline.run_market_pipeline.fetch_kalshi_markets", fail_network)

    out = run_market_pipeline(use_fixture=True)
    payload = json.loads(out.read_text(encoding="utf-8"))
    parquet_path = processed / "prediction_markets.parquet"
    df = pd.read_parquet(parquet_path)

    assert out == processed / "market_opportunities.json"
    assert {"meta", "data_source", "hero_pick", "opportunities", "edge_summary"}.issubset(payload)
    assert payload["data_source"] == "fixture_fallback"
    assert payload["hero_pick"] is not None
    assert len(payload["opportunities"]) > 0
    assert parquet_path.exists()
    assert {"market_id", "question", "market_price", "model_prob", "venue", "closes_at"}.issubset(df.columns)
    assert pd.api.types.is_float_dtype(df["market_price"])
    assert pd.api.types.is_float_dtype(df["model_prob"])
