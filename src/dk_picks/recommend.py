import json
from pathlib import Path

import pandas as pd

from dk_picks.config import settings
from dk_picks.db.models import PickLog
from dk_picks.db.session import get_session
from dk_picks.models.predict import predict_proba
from dk_picks.portfolio.parlay import build_parlay_slips, rank_singles

SPORT_MODEL_MAP = {
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "mlb": "baseball_mlb",
    "nhl": "ice_hockey_nhl",
}


def generate_recommendations(
    sports: list[str] | None = None,
    bankroll: float | None = None,
    max_parlays: int = 10,
    markets: list[str] | None = None,
) -> dict:
    bankroll = bankroll or settings.default_bankroll
    sports = sports or ["nba", "nfl"]
    markets = markets or ["h2h", "spreads"]

    all_singles = []
    all_parlays = []

    for sport in sports:
        sport_key = SPORT_MODEL_MAP.get(sport.lower(), sport)
        for market in markets:
            try:
                df = predict_proba(sport_key, market)
            except FileNotFoundError:
                continue
            if df.empty:
                continue
            singles = rank_singles(df, bankroll)
            if not singles.empty:
                all_singles.append(singles)
            parlays = build_parlay_slips(df, bankroll, max_parlays=max_parlays)
            all_parlays.extend(parlays)

    singles_df = (
        pd.concat(all_singles, ignore_index=True).sort_values("ev", ascending=False)
        if all_singles
        else pd.DataFrame()
    )
    all_parlays.sort(key=lambda x: x["edge"], reverse=True)

    return {
        "bankroll": bankroll,
        "singles": singles_df,
        "parlays": all_parlays[:max_parlays],
    }


def persist_recommendations(rec: dict) -> int:
    session = get_session()
    n = 0
    try:
        for row in rec.get("singles", pd.DataFrame()).itertuples():
            session.add(
                PickLog(
                    sport=row.sport,
                    event_id=row.event_id,
                    market=row.market,
                    selection=row.outcome,
                    model_prob=float(row.model_prob),
                    fair_prob=float(row.fair_prob),
                    edge=float(row.edge),
                    stake=float(row.stake),
                    odds_american=int(row.price_american),
                    is_parlay=False,
                )
            )
            n += 1
        for i, p in enumerate(rec.get("parlays", [])):
            pid = f"parlay_{i}"
            for leg in p["legs"]:
                session.add(
                    PickLog(
                        sport="multi",
                        event_id=pid,
                        market="parlay",
                        selection=leg,
                        model_prob=p["joint_prob"],
                        fair_prob=p["joint_prob"] - p["edge"],
                        edge=p["edge"],
                        stake=p["stake"],
                        odds_american=p["approx_odds"],
                        is_parlay=True,
                        parlay_id=pid,
                    )
                )
                n += 1
        session.commit()
    finally:
        session.close()
    return n


def export_json(rec: dict, path: Path) -> None:
    singles = rec.get("singles", pd.DataFrame())
    payload = {
        "bankroll": rec["bankroll"],
        "singles": singles.head(20).to_dict(orient="records") if not singles.empty else [],
        "parlays": rec.get("parlays", []),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
