from datetime import datetime, timezone

import httpx

from dk_picks.config import settings
from dk_picks.db.models import OddsSnapshot
from dk_picks.db.session import get_session
from dk_picks.odds import american_to_implied, devig_two_way

ODDS_API_BASE = "https://api.the-odds-api.com/v4"

SPORT_KEYS = {
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "mlb": "baseball_mlb",
    "nhl": "ice_hockey_nhl",
}


def ingest_odds_from_api(sport: str, markets: str = "h2h,spreads,totals") -> int:
    key = settings.odds_api_key
    if not key:
        raise ValueError("Set ODDS_API_KEY in .env (https://the-odds-api.com/)")

    sport_key = SPORT_KEYS.get(sport.lower(), sport)
    url = f"{ODDS_API_BASE}/sports/{sport_key}/odds"
    params = {
        "apiKey": key,
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american",
        "bookmakers": "draftkings",
    }

    with httpx.Client(timeout=30) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        events = resp.json()

    session = get_session()
    count = 0
    try:
        for event in events:
            event_id = event["id"]
            home = event["home_team"]
            away = event["away_team"]
            commence = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))

            for book in event.get("bookmakers", []):
                if book["key"] != "draftkings":
                    continue
                for market in book.get("markets", []):
                    market_key = market["key"]
                    outcomes = market.get("outcomes", [])
                    implied = [american_to_implied(int(o["price"])) for o in outcomes]
                    fair_list = list(implied)
                    if len(implied) == 2:
                        fair_list = list(devig_two_way(implied[0], implied[1]))

                    for outcome, imp, fair in zip(outcomes, implied, fair_list):
                        row = OddsSnapshot(
                            sport=sport_key,
                            event_id=event_id,
                            home_team=home,
                            away_team=away,
                            commence_time=commence,
                            market=market_key,
                            outcome=outcome["name"],
                            bookmaker="draftkings",
                            price_american=int(outcome["price"]),
                            point=outcome.get("point"),
                            implied_prob=imp,
                            fair_prob=fair,
                            captured_at=datetime.now(timezone.utc),
                        )
                        session.add(row)
                        count += 1
        session.commit()
    finally:
        session.close()
    return count
