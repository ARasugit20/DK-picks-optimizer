from pathlib import Path

import pandas as pd

from dk_picks.db.models import PickLog, TeamStat
from dk_picks.db.session import get_session


def import_stats_csv(path: Path, sport: str) -> int:
    """CSV columns: team, as_of_date, off_rating, def_rating, pace, win_pct, rest_days, is_home"""
    df = pd.read_csv(path)
    session = get_session()
    n = 0
    try:
        for _, row in df.iterrows():
            session.add(
                TeamStat(
                    sport=sport,
                    team=str(row["team"]),
                    as_of_date=pd.to_datetime(row["as_of_date"]).to_pydatetime(),
                    games_played=int(row.get("games_played", 0)),
                    off_rating=float(row.get("off_rating", 0)),
                    def_rating=float(row.get("def_rating", 0)),
                    pace=float(row.get("pace", 0)),
                    win_pct=float(row.get("win_pct", 0)),
                    rest_days=int(row.get("rest_days", 1)),
                    is_home=bool(row.get("is_home", False)),
                )
            )
            n += 1
        session.commit()
    finally:
        session.close()
    return n


def import_results_csv(path: Path) -> int:
    """Update pick_logs by id: id, result, clv (optional)"""
    df = pd.read_csv(path)
    session = get_session()
    n = 0
    try:
        for _, row in df.iterrows():
            pick = session.get(PickLog, int(row["id"]))
            if pick:
                pick.result = str(row["result"])
                if "clv" in row and pd.notna(row["clv"]):
                    pick.clv = float(row["clv"])
                n += 1
        session.commit()
    finally:
        session.close()
    return n
