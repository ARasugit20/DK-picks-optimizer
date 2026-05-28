"""Fetch NBA player season averages from ESPN for prop projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
ESPN_ATHLETE_STATS = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/stats"

KEY_PLAYERS: dict[str, list[str]] = {
    "Oklahoma City Thunder": [
        "Shai Gilgeous-Alexander",
        "Chet Holmgren",
        "Jalen Williams",
        "Isaiah Hartenstein",
        "Luguentz Dort",
        "Alex Caruso",
        "Isaiah Joe",
    ],
    "San Antonio Spurs": [
        "Victor Wembanyama",
        "De'Aaron Fox",
        "Stephon Castle",
        "Devin Vassell",
        "Harrison Barnes",
        "Julian Champagnie",
        "Keldon Johnson",
    ],
}


@dataclass
class PlayerAverages:
    player: str
    team: str
    event_id: str
    home_team: str
    away_team: str
    pts: float
    reb: float
    ast: float
    fg3m: float
    min: float
    stl: float
    blk: float
    games: int = 0


def find_event(match_filter: str | None = None, date: str | None = None) -> dict:
    """Find NBA event. date format: YYYYMMDD (e.g. 20260528)."""
    params: dict = {}
    if date:
        params["dates"] = date.replace("-", "")
    resp = httpx.get(ESPN_SCOREBOARD, params=params, timeout=30)
    resp.raise_for_status()
    events = resp.json().get("events", [])
    if not events and not date:
        today = datetime.now().strftime("%Y%m%d")
        resp = httpx.get(ESPN_SCOREBOARD, params={"dates": today}, timeout=30)
        resp.raise_for_status()
        events = resp.json().get("events", [])

    for event in events:
        name = event.get("name", "")
        if match_filter and match_filter.lower() not in name.lower():
            continue
        comp = event["competitions"][0]
        home = next(t for t in comp["competitors"] if t["homeAway"] == "home")
        away = next(t for t in comp["competitors"] if t["homeAway"] == "away")
        odds = (comp.get("odds") or [{}])[0]
        return {
            "event_id": event["id"],
            "name": name,
            "date": event.get("date"),
            "home_team": home["team"]["displayName"],
            "away_team": away["team"]["displayName"],
            "home_id": home["team"]["id"],
            "away_id": away["team"]["id"],
            "spread": odds.get("spread"),
            "total": odds.get("overUnder"),
            "odds_details": odds.get("details"),
        }
    raise ValueError(f"No NBA game found for filter={match_filter!r} date={date!r}")


def _parse_made_attempted(val: str) -> float:
    if "-" in val:
        return float(val.split("-")[0])
    return float(val)


def _parse_athlete_stats(payload: dict) -> dict[str, float]:
    for cat in payload.get("categories", []):
        label = (cat.get("displayName") or "").lower()
        if "average" not in label:
            continue
        names = cat.get("names") or []
        stats_rows = cat.get("statistics") or []
        if not names or not stats_rows:
            continue
        values = stats_rows[0].get("stats") or []
        if len(values) != len(names):
            continue
        raw = dict(zip(names, values))
        try:
            fg3_key = "avgThreePointFieldGoalsMade-avgThreePointFieldGoalsAttempted"
            fg3m = _parse_made_attempted(raw.get(fg3_key, "0"))
            return {
                "pts": float(raw.get("avgPoints", 0)),
                "reb": float(raw.get("avgRebounds", 0)),
                "ast": float(raw.get("avgAssists", 0)),
                "fg3m": fg3m,
                "min": float(raw.get("avgMinutes", 0)),
                "stl": float(raw.get("avgSteals", 0)),
                "blk": float(raw.get("avgBlocks", 0)),
                "games": int(float(raw.get("gamesPlayed", 0))),
            }
        except (TypeError, ValueError):
            continue
    return {}


def fetch_player_averages(athlete_id: str) -> dict[str, float]:
    for st in (3, 2):  # postseason, regular season
        url = ESPN_ATHLETE_STATS.format(id=athlete_id)
        resp = httpx.get(url, params={"seasontype": st}, timeout=30)
        if resp.status_code != 200:
            continue
        parsed = _parse_athlete_stats(resp.json())
        if parsed.get("pts", 0) > 0 and parsed.get("min", 0) >= 5:
            return parsed
    return {}


def _stats_from_summary_leaders(summary: dict, team_name: str) -> dict[str, dict]:
    """Pull per-player averages from game summary leader blocks."""
    out: dict[str, dict] = {}
    for block in summary.get("leaders") or []:
        if block.get("team", {}).get("displayName") != team_name:
            continue
        for cat in block.get("leaders") or []:
            for leader in cat.get("leaders") or []:
                athlete = leader.get("athlete") or {}
                name = athlete.get("displayName")
                if not name:
                    continue
                entry = out.setdefault(
                    name,
                    {"id": str(athlete.get("id", "")), "pts": 0, "reb": 0, "ast": 0, "min": 0, "fg3m": 0, "stl": 0, "blk": 0},
                )
                for s in leader.get("statistics") or []:
                    key = s.get("name", "")
                    val = float(s.get("value", 0))
                    if key == "avgPoints":
                        entry["pts"] = val
                    elif key == "avgRebounds":
                        entry["reb"] = val
                    elif key == "avgAssists":
                        entry["ast"] = val
                    elif key == "avgMinutes":
                        entry["min"] = val
                    elif key == "avgSteals":
                        entry["stl"] = val
                    elif key == "avgBlocks":
                        entry["blk"] = val
    return out


def _roster_athletes(team_id: str) -> list[dict]:
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json().get("athletes") or []


def load_fixture_players(event: dict) -> list[PlayerAverages]:
    summary = httpx.get(ESPN_SUMMARY, params={"event": event["event_id"]}, timeout=30).json()
    players: list[PlayerAverages] = []

    for team_name, team_id in (
        (event["home_team"], event["home_id"]),
        (event["away_team"], event["away_id"]),
    ):
        leader_map = _stats_from_summary_leaders(summary, team_name)
        key_names = set(KEY_PLAYERS.get(team_name, []))
        roster = _roster_athletes(team_id)
        roster_by_name = {a.get("displayName"): a for a in roster}

        for name in key_names:
            ath = roster_by_name.get(name)
            if not ath:
                continue
            status = (ath.get("status") or {}).get("type", "")
            if status and status not in ("active", "Active"):
                continue
            aid = str(ath.get("id", ""))
            stats = fetch_player_averages(aid) if aid else {}
            leader_stats = leader_map.get(name, {})
            # Prefer game-summary playoff leaders when API returns incomplete data
            for k in ("pts", "reb", "ast", "min", "fg3m", "stl", "blk"):
                lv = leader_stats.get(k, 0)
                sv = stats.get(k, 0)
                if lv > 0:
                    stats[k] = lv
                elif sv:
                    stats[k] = sv
            if not stats or stats.get("min", 0) < 8:
                continue
            players.append(
                PlayerAverages(
                    player=name,
                    team=team_name,
                    event_id=event["event_id"],
                    home_team=event["home_team"],
                    away_team=event["away_team"],
                    pts=stats.get("pts", 0),
                    reb=stats.get("reb", 0),
                    ast=stats.get("ast", 0),
                    fg3m=stats.get("fg3m", 0),
                    min=stats.get("min", 0),
                    stl=stats.get("stl", 0),
                    blk=stats.get("blk", 0),
                    games=int(stats.get("games", 0)),
                )
            )
    return players
