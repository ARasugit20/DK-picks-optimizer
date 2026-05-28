from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import select

from dk_picks.db.models import OddsSnapshot, TeamStat
from dk_picks.db.session import get_session


def _latest_team_stats(session, sport: str, team: str) -> dict:
    q = (
        select(TeamStat)
        .where(TeamStat.sport == sport, TeamStat.team == team)
        .order_by(TeamStat.as_of_date.desc())
        .limit(1)
    )
    row = session.execute(q).scalars().first()
    if not row:
        return {
            "off_rating": 0.0,
            "def_rating": 0.0,
            "pace": 0.0,
            "win_pct": 0.5,
            "rest_days": 1,
        }
    return {
        "off_rating": row.off_rating,
        "def_rating": row.def_rating,
        "pace": row.pace,
        "win_pct": row.win_pct,
        "rest_days": row.rest_days,
    }


def build_feature_matrix(sport: str | None = None) -> pd.DataFrame:
    """Join latest odds with team stats into model-ready rows."""
    session = get_session()
    try:
        q = select(OddsSnapshot).order_by(OddsSnapshot.captured_at.desc())
        if sport:
            q = q.where(OddsSnapshot.sport.contains(sport))
        odds_rows = session.execute(q).scalars().all()
    finally:
        session.close()

    if not odds_rows:
        return pd.DataFrame()

    records = []
    seen = set()
    for o in odds_rows:
        key = (o.event_id, o.market, o.outcome)
        if key in seen:
            continue
        seen.add(key)

        session = get_session()
        try:
            home_s = _latest_team_stats(session, o.sport, o.home_team)
            away_s = _latest_team_stats(session, o.sport, o.away_team)
        finally:
            session.close()

        rating_diff = home_s["off_rating"] - away_s["def_rating"]
        opp_rating_diff = away_s["off_rating"] - home_s["def_rating"]
        rest_adv = home_s["rest_days"] - away_s["rest_days"]
        pace_avg = (home_s["pace"] + away_s["pace"]) / 2
        win_pct_diff = home_s["win_pct"] - away_s["win_pct"]

        # Outcome-specific edges (critical for per-side predictions)
        is_home_pick = o.outcome == o.home_team
        is_away_pick = o.outcome == o.away_team
        team_rating_edge = rating_diff if is_home_pick else opp_rating_diff if is_away_pick else 0.0
        team_win_edge = win_pct_diff if is_home_pick else -win_pct_diff if is_away_pick else 0.0
        rest_edge = rest_adv if is_home_pick else -rest_adv if is_away_pick else 0.0
        home_court = 1.0 if is_home_pick else -1.0 if is_away_pick else 0.0

        if o.market == "totals":
            over_pick = o.outcome.lower() == "over"
            pace_edge = (pace_avg - 98.0) / 10.0
            team_rating_edge = pace_edge if over_pick else -pace_edge
            team_win_edge = 0.0
            home_court = 0.0

        records.append(
            {
                "event_id": o.event_id,
                "sport": o.sport,
                "home_team": o.home_team,
                "away_team": o.away_team,
                "commence_time": o.commence_time,
                "market": o.market,
                "outcome": o.outcome,
                "point": o.point or 0.0,
                "price_american": o.price_american,
                "implied_prob": o.implied_prob,
                "fair_prob": o.fair_prob,
                "rating_diff": rating_diff,
                "opp_rating_diff": opp_rating_diff,
                "pace_avg": pace_avg,
                "win_pct_diff": win_pct_diff,
                "rest_adv": rest_adv,
                "team_rating_edge": team_rating_edge,
                "team_win_edge": team_win_edge,
                "rest_edge": rest_edge,
                "home_court": home_court,
                "label": np.nan,
            }
        )

    return pd.DataFrame(records)


FEATURE_COLS = [
    "implied_prob",
    "fair_prob",
    "point",
    "team_rating_edge",
    "team_win_edge",
    "rest_edge",
    "home_court",
    "pace_avg",
]
