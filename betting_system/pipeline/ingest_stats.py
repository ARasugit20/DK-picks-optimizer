"""NBA player game log ingestion via nba_api."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import pandas as pd

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger


logger = get_logger(__name__)

STAT_COLUMNS = {
    "points": "PTS",
    "assists": "AST",
    "rebounds": "REB",
}

MARKET_TO_STAT = {
    "player_points_over": "points",
    "player_points_under": "points",
    "player_assists_over": "assists",
    "player_assists_under": "assists",
    "player_rebounds_over": "rebounds",
    "player_rebounds_under": "rebounds",
}


def _parse_minutes(val: Any) -> float:
    """Convert NBA MIN column (e.g. '32:15') to float minutes."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    s = str(val)
    if ":" in s:
        parts = s.split(":")
        try:
            return float(parts[0]) + float(parts[1]) / 60.0
        except (ValueError, IndexError):
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _season_to_nba_api(season: str) -> str:
    """Convert '2024-25' to nba_api season format."""
    if len(season) == 7 and "-" in season:
        return season
    raise ValueError(f"Invalid season format: {season}. Use e.g. 2024-25")


def fetch_league_game_logs(season: str, *, cache_dir: Path | None = None) -> pd.DataFrame:
    """Fetch league-wide player game logs from nba_api with optional disk cache."""
    season_fmt = _season_to_nba_api(season)
    cache_path = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"league_game_log_{season_fmt.replace('-', '_')}.parquet"
        if cache_path.exists():
            logger.info("Loading cached game logs from %s", cache_path)
            return pd.read_parquet(cache_path)

    try:
        from nba_api.stats.endpoints import leaguegamelog
    except ImportError as exc:
        raise ImportError("Install nba_api: pip install nba_api") from exc

    logger.info("Fetching NBA league game logs for season %s", season_fmt)
    time.sleep(0.6)
    log = leaguegamelog.LeagueGameLog(
        season=season_fmt,
        season_type_all_star="Regular Season",
        player_or_team_abbreviation="P",
    )
    df = log.get_data_frames()[0]
    if cache_path is not None:
        df.to_parquet(cache_path, index=False)
    return df


def normalize_game_logs(raw: pd.DataFrame, *, season: str) -> pd.DataFrame:
    """Normalize nba_api league game log to long-format stat rows."""
    rows: list[dict[str, Any]] = []
    for _, r in raw.iterrows():
        game_id = str(r.get("GAME_ID", ""))
        player_id = str(r.get("PLAYER_ID", ""))
        player_name = str(r.get("PLAYER_NAME", ""))
        team_id = str(r.get("TEAM_ID", ""))
        team_abbr = str(r.get("TEAM_ABBREVIATION", ""))
        matchup = str(r.get("MATCHUP", ""))
        home_away = "home" if " vs. " in matchup else "away"
        opponent = matchup.split(" vs. ")[-1].split(" @ ")[-1].strip() if matchup else ""
        game_date = pd.to_datetime(r.get("GAME_DATE")).date()
        minutes = _parse_minutes(r.get("MIN"))

        for stat_type, col in STAT_COLUMNS.items():
            if col not in r.index:
                continue
            actual = float(r[col]) if pd.notna(r[col]) else 0.0
            rows.append(
                {
                    "game_id": game_id,
                    "player_id": player_id,
                    "player_name": player_name,
                    "team_id": team_id,
                    "team_abbr": team_abbr,
                    "opponent_team_abbr": opponent,
                    "stat_type": stat_type,
                    "actual_value": actual,
                    "game_date": game_date,
                    "minutes": minutes,
                    "home_away": home_away,
                    "season": season,
                }
            )
    return pd.DataFrame(rows)


def attach_hit_labels(stat_df: pd.DataFrame, odds_path: str | Path | None = None) -> pd.DataFrame:
    """Join historical lines from odds parquet and compute hit labels."""
    df = stat_df.copy()
    df["hit"] = pd.NA

    if odds_path is None or not Path(odds_path).exists():
        logger.warning("No odds file for hit labels; hit column left NA (use --no-lines mode)")
        df["hit"] = False
        return df

    odds = pd.read_parquet(odds_path)
    if "game_date" in odds.columns:
        odds["game_date"] = pd.to_datetime(odds["game_date"], errors="coerce").dt.date

    for idx, row in df.iterrows():
        stat_type = row["stat_type"]
        over_market = f"player_{stat_type}_over"
        under_market = f"player_{stat_type}_under"
        mask = (
            (odds["player_id"].astype(str) == str(row["player_id"]))
            & (odds["game_id"].astype(str) == str(row["game_id"]))
        )
        matched = odds[mask]
        if matched.empty:
            continue
        over_rows = matched[matched["market_type"] == over_market]
        if not over_rows.empty:
            line = float(over_rows.iloc[0]["line"])
            df.at[idx, "hit"] = float(row["actual_value"]) > line
        else:
            under_rows = matched[matched["market_type"] == under_market]
            if not under_rows.empty:
                line = float(under_rows.iloc[0]["line"])
                df.at[idx, "hit"] = float(row["actual_value"]) < line

    df["hit"] = df["hit"].fillna(False).astype(bool)
    return df


def ingest_nba_stats(
    *,
    season: str = "2024-25",
    odds_path: str | Path | None = None,
    no_lines: bool = False,
    out_path: str | Path | None = None,
    use_fixture: bool = False,
) -> Path:
    """Ingest NBA stats and write stat_results.parquet.

    Args:
        season: NBA season string e.g. 2024-25.
        odds_path: Optional odds parquet to compute hit labels.
        no_lines: Skip hit label join (logs only).
        out_path: Output parquet path.
        use_fixture: Use bundled fixture instead of live API (for tests/CI).

    Returns:
        Path to stat_results.parquet.
    """
    settings = load_settings()
    processed = Path(settings.data["processed_data_path"])
    raw_dir = Path(settings.data["raw_data_path"]) / "nba_api"
    processed.mkdir(parents=True, exist_ok=True)
    out_path = Path(out_path) if out_path else processed / "stat_results.parquet"

    if use_fixture:
        fixture = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "nba_stat_results_fixture.parquet"
        if not fixture.exists():
            from betting_system.pipeline.fixtures_loader import write_nba_stats_fixture

            write_nba_stats_fixture(fixture)
        stat_df = pd.read_parquet(fixture)
    else:
        raw = fetch_league_game_logs(season, cache_dir=raw_dir)
        stat_df = normalize_game_logs(raw, season=season)

    if not no_lines and odds_path is not None:
        stat_df = attach_hit_labels(stat_df, odds_path=odds_path)
    elif no_lines:
        stat_df["hit"] = False

    stat_df.to_parquet(out_path, index=False)
    logger.info("Wrote stat_results: %s (%d rows)", out_path, len(stat_df))
    return out_path


def main() -> None:
    """CLI entrypoint for stats ingestion."""
    parser = argparse.ArgumentParser(description="Ingest NBA player game logs")
    parser.add_argument("--season", default="2024-25", help="NBA season e.g. 2024-25")
    parser.add_argument("--odds-path", default=None, help="Odds parquet for hit labels")
    parser.add_argument("--no-lines", action="store_true", help="Skip hit label computation")
    parser.add_argument("--fixture", action="store_true", help="Use bundled fixture (no API)")
    args = parser.parse_args()
    ingest_nba_stats(
        season=args.season,
        odds_path=args.odds_path,
        no_lines=args.no_lines,
        use_fixture=args.fixture,
    )


if __name__ == "__main__":
    main()
