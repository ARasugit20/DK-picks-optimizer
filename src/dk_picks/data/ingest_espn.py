"""Ingest today's NBA odds from ESPN (DraftKings lines) when ODDS_API_KEY is unavailable."""

from datetime import datetime, timezone

import httpx

from dk_picks.db.models import OddsSnapshot, TeamStat
from dk_picks.db.session import get_session
from dk_picks.odds import american_to_implied, devig_two_way

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# Approximate postseason ratings for demo when stats CSV not loaded (OKC, SAS)
DEFAULT_TEAM_STATS: dict[str, dict] = {
    "Oklahoma City Thunder": {
        "off_rating": 119.2,
        "def_rating": 106.8,
        "pace": 98.0,
        "win_pct": 0.78,
        "rest_days": 2,
    },
    "San Antonio Spurs": {
        "off_rating": 115.5,
        "def_rating": 109.1,
        "pace": 99.5,
        "win_pct": 0.62,
        "rest_days": 2,
    },
}


def _parse_events(payload: dict) -> list[dict]:
    events = []
    for event in payload.get("events", []):
        comp = event["competitions"][0]
        home = next(t for t in comp["competitors"] if t["homeAway"] == "home")
        away = next(t for t in comp["competitors"] if t["homeAway"] == "away")
        odds_list = comp.get("odds") or []
        if not odds_list:
            continue
        o = odds_list[0]
        spread = o.get("spread")
        total = o.get("overUnder")
        if spread is None or total is None:
            continue
        events.append(
            {
                "event_id": event["id"],
                "name": event["name"],
                "commence": datetime.fromisoformat(event["date"].replace("Z", "+00:00")),
                "home_team": home["team"]["displayName"],
                "away_team": away["team"]["displayName"],
                "spread_home": float(spread),
                "total": float(total),
            }
        )
    return events


def ingest_today_from_espn(match_filter: str | None = None) -> list[str]:
    """
    Load ESPN scoreboard into odds_snapshots + team_stats.
    match_filter: substring match on event name, e.g. 'Thunder' or 'Spurs'.
    """
    resp = httpx.get(ESPN_SCOREBOARD, timeout=30)
    resp.raise_for_status()
    events = _parse_events(resp.json())
    if match_filter:
        events = [e for e in events if match_filter.lower() in e["name"].lower()]

    if not events:
        raise ValueError("No games with odds found on ESPN scoreboard for filter.")

    session = get_session()
    ingested: list[str] = []
    now = datetime.now(timezone.utc)
    sport = "basketball_nba"

    try:
        # Replace prior snapshots for events we are reloading
        event_ids = [ev["event_id"] for ev in events]
        if event_ids:
            session.query(OddsSnapshot).filter(
                OddsSnapshot.event_id.in_(event_ids)
            ).delete(synchronize_session=False)
        for ev in events:
            eid = ev["event_id"]
            home, away = ev["home_team"], ev["away_team"]
            spread = ev["spread_home"]
            total = ev["total"]

            for team, is_home in ((home, True), (away, False)):
                stats = DEFAULT_TEAM_STATS.get(team, {})
                session.add(
                    TeamStat(
                        sport=sport,
                        team=team,
                        as_of_date=now,
                        games_played=10,
                        off_rating=stats.get("off_rating", 112.0),
                        def_rating=stats.get("def_rating", 110.0),
                        pace=stats.get("pace", 98.0),
                        win_pct=stats.get("win_pct", 0.5),
                        rest_days=stats.get("rest_days", 2),
                        is_home=is_home,
                    )
                )

            # Spread: home line from ESPN (e.g. -2.5 => home favored)
            for outcome, point in ((home, spread), (away, -spread)):
                for price in (-110,):
                    imp = american_to_implied(price)
                    fair_a, fair_b = devig_two_way(
                        american_to_implied(-110), american_to_implied(-110)
                    )
                    fair = fair_a if outcome == home else fair_b
                    session.add(
                        OddsSnapshot(
                            sport=sport,
                            event_id=eid,
                            home_team=home,
                            away_team=away,
                            commence_time=ev["commence"],
                            market="spreads",
                            outcome=outcome,
                            price_american=price,
                            point=point,
                            implied_prob=imp,
                            fair_prob=fair,
                            captured_at=now,
                        )
                    )

            # Totals
            for outcome in (f"Over {total}", f"Under {total}"):
                imp = american_to_implied(-110)
                fair_a, fair_b = devig_two_way(imp, imp)
                fair = fair_a if "Over" in outcome else fair_b
                session.add(
                    OddsSnapshot(
                        sport=sport,
                        event_id=eid,
                        home_team=home,
                        away_team=away,
                        commence_time=ev["commence"],
                        market="totals",
                        outcome=outcome.split()[0],
                        price_american=-110,
                        point=total,
                        implied_prob=imp,
                        fair_prob=fair,
                        captured_at=now,
                    )
                )

            # H2H (approximate ML from spread; replace when Odds API available)
            fav, dog = (home, away) if spread < 0 else (away, home)
            ml = {fav: -140, dog: +120}
            imps = [american_to_implied(ml[fav]), american_to_implied(ml[dog])]
            fair_fav, fair_dog = devig_two_way(imps[0], imps[1])
            for team, price, fair in (
                (fav, ml[fav], fair_fav),
                (dog, ml[dog], fair_dog),
            ):
                session.add(
                    OddsSnapshot(
                        sport=sport,
                        event_id=eid,
                        home_team=home,
                        away_team=away,
                        commence_time=ev["commence"],
                        market="h2h",
                        outcome=team,
                        price_american=price,
                        point=None,
                        implied_prob=american_to_implied(price),
                        fair_prob=fair,
                        captured_at=now,
                    )
                )

            ingested.append(ev["name"])

        session.commit()
    finally:
        session.close()

    return ingested
