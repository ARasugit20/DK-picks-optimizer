"""NBA stats ingestion tests."""

from __future__ import annotations

import os

import pandas as pd
import pytest
import yaml

from betting_system.pipeline.ingest_stats import ingest_nba_stats, normalize_game_logs


@pytest.fixture
def stats_config(tmp_path, repo_root):
    raw = yaml.safe_load((repo_root / "betting_system" / "config.yaml").read_text(encoding="utf-8"))
    processed = tmp_path / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    raw["data"]["processed_data_path"] = str(processed) + "/"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump(raw), encoding="utf-8")
    return cfg


def test_ingest_stats_fixture_writes_required_columns(stats_config):
    """Fixture mode produces stat_results with required schema."""
    os.environ["BETTING_CONFIG_PATH"] = str(stats_config)
    out = ingest_nba_stats(use_fixture=True, no_lines=True)
    df = pd.read_parquet(out)
    required = {
        "game_id", "player_id", "player_name", "stat_type", "actual_value",
        "hit", "game_date", "minutes", "home_away", "opponent_team_abbr",
    }
    assert required.issubset(set(df.columns))
    assert len(df) > 0


def test_normalize_game_logs_from_sample():
    """normalize_game_logs maps nba_api columns to long format."""
    raw = pd.DataFrame(
        {
            "GAME_ID": ["001"],
            "PLAYER_ID": [2544],
            "PLAYER_NAME": ["LeBron James"],
            "TEAM_ID": [1610612747],
            "TEAM_ABBREVIATION": ["LAL"],
            "MATCHUP": ["LAL vs. BOS"],
            "GAME_DATE": ["2024-01-01"],
            "MIN": ["35:00"],
            "PTS": [28],
            "AST": [8],
            "REB": [7],
        }
    )
    out = normalize_game_logs(raw, season="2024-25")
    assert set(out["stat_type"]) == {"points", "assists", "rebounds"}
    assert out.loc[out["stat_type"] == "points", "actual_value"].iloc[0] == 28.0
    assert out.iloc[0]["home_away"] == "home"


def test_parse_minutes_and_attach_hit_labels(tmp_path):
    """Minutes parsing and hit labels from odds parquet."""
    from betting_system.pipeline.ingest_stats import _parse_minutes, attach_hit_labels

    assert _parse_minutes("32:30") == pytest.approx(32.5)
    assert _parse_minutes(None) == 0.0

    stat = pd.DataFrame(
        {
            "game_id": ["g1"],
            "player_id": ["p1"],
            "stat_type": ["points"],
            "actual_value": [30.0],
            "game_date": [pd.Timestamp("2024-01-01").date()],
        }
    )
    odds = pd.DataFrame(
        {
            "game_id": ["g1"],
            "player_id": ["p1"],
            "market_type": ["player_points_over"],
            "line": [25.5],
        }
    )
    odds_path = tmp_path / "odds.parquet"
    odds.to_parquet(odds_path)
    labeled = attach_hit_labels(stat, odds_path=odds_path)
    assert bool(labeled.iloc[0]["hit"]) is True
