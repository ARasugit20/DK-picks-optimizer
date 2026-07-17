from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger, utcnow
from betting_system.odds_math import implied_prob_from_american
from betting_system.schemas import OddsRecord


logger = get_logger(__name__)


@retry(wait=wait_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(5))
def _get_json(client: httpx.Client, url: str, params: dict[str, Any]) -> Any:
    r = client.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _write_raw_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    # Spec: dedupe on (game_id, market_type, line, timestamp)
    # We include player_id for safety since many markets are player-scoped.
    cols = ["game_id", "market_type", "player_id", "line", "ingested_at"]
    for c in cols:
        if c not in df.columns:
            raise ValueError(f"Missing required column for dedupe: {c}")
    return df.drop_duplicates(subset=cols, keep="last").reset_index(drop=True)


def _validate_odds_records(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for r in rows:
        obj = OddsRecord.model_validate(r)
        validated.append(obj.model_dump())
    return validated


def ingest_odds_nba_player_props(
    *,
    date: str,
    regions: str = "us",
    markets: str = "player_points,player_rebounds,player_assists",
    odds_format: str = "american",
    bookmakers: str | None = None,
) -> Path:
    """
    Pull NBA player prop odds from The Odds API and persist:
    - raw JSON (with ingested_at timestamp)
    - parsed parquet of normalized OddsRecord rows

    NOTE: The Odds API response schemas vary by endpoint and plan tier.
    This implementation is a robust "normalizer shell": it records raw payloads,
    and extracts records where fields are present, while failing loudly if none are parsed.
    """
    settings = load_settings()
    api_key = settings.data.get("odds_api_key", "")
    if not api_key:
        raise ValueError("Missing ODDS_API_KEY (set env var or config.yaml data.odds_api_key)")

    if bookmakers is None:
        bookmakers = settings.raw.get("odds", {}).get(
            "bookmakers", "draftkings,fanduel,williamhill_us"
        )

    ingested_at = utcnow()
    raw_dir = Path(settings.data["raw_data_path"]) / "odds_api"
    out_dir = Path(settings.data["odds_history_path"]) / "odds_api"
    raw_path = raw_dir / f"nba_props_{date}_{ingested_at.isoformat().replace(':','')}.json"

    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
        "dateFormat": "iso",
        "bookmakers": bookmakers,
        "date": date,
    }

    logger.info("Fetching odds from The Odds API")
    with httpx.Client() as client:
        payload = _get_json(client, url, params)

    _write_raw_json(raw_path, {"ingested_at": ingested_at.isoformat(), "payload": payload})

    # Normalize as best-effort (varies across API tiers).
    rows: list[dict[str, Any]] = []
    for game in payload if isinstance(payload, list) else []:
        game_id = str(game.get("id") or game.get("game_id") or "")
        if not game_id:
            continue
        for bm in game.get("bookmakers", []) or []:
            bookmaker = str(bm.get("key") or bm.get("title") or "unknown")
            for market in bm.get("markets", []) or []:
                market_key = str(market.get("key") or "")
                # outcomes for props sometimes contain player + point
                for outcome in market.get("outcomes", []) or []:
                    # Attempt to capture: player name/id, line, odds
                    odds_am = outcome.get("price")
                    line = outcome.get("point")
                    player = outcome.get("description") or outcome.get("name") or ""
                    side = outcome.get("name") or outcome.get("type") or ""

                    if odds_am is None or line is None or not player:
                        continue
                    try:
                        odds_am = int(odds_am)
                        line_f = float(line)
                    except Exception:
                        continue

                    # Map market+side into your canonical market_type
                    # Example: market_key "player_points" with outcome side "Over"/"Under"
                    market_type = f"{market_key}_{str(side).strip().lower()}"
                    market_type = market_type.replace(" ", "_")

                    rec = {
                        "game_id": game_id,
                        "market_type": market_type,
                        "player_id": str(player),
                        "line": line_f,
                        "odds_american": odds_am,
                        "implied_prob": float(implied_prob_from_american(odds_am)),
                        "bookmaker": bookmaker,
                        "ingested_at": ingested_at,
                        "is_closing": False,
                    }
                    rows.append(rec)

    if not rows:
        raise RuntimeError(
            "Parsed 0 odds rows from The Odds API payload. "
            "This usually means the endpoint/plan doesn't include these prop markets or response schema differs. "
            f"Raw saved at: {raw_path}"
        )

    validated = _validate_odds_records(rows)
    df = pd.DataFrame(validated)
    df = _dedupe(df)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"nba_props_{date}_{ingested_at.date().isoformat()}.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("Wrote %d odds rows to %s", len(df), out_path)
    return out_path

