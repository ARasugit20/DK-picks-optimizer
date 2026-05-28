"""Project player props and recommend Over/Under vs sportsbook-style lines."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from dk_picks.data.player_stats_espn import PlayerAverages, find_event, load_fixture_players
from dk_picks.odds import american_to_implied, expected_value
from dk_picks.portfolio.kelly import kelly_stake

PROP_STD = {
    "points": 6.0,
    "rebounds": 2.6,
    "assists": 2.0,
    "threes": 1.3,
    "steals": 0.8,
    "blocks": 0.9,
    "pts+reb+ast": 8.5,
}

PROP_FIELDS = {
    "points": "pts",
    "rebounds": "reb",
    "assists": "ast",
    "threes": "fg3m",
    "steals": "stl",
    "blocks": "blk",
}


@dataclass
class PropPick:
    player: str
    team: str
    prop: str
    line: float
    projection: float
    pick: str
    prob: float
    edge: float
    ev: float
    stake: float
    confidence: str


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def prob_over(projection: float, line: float, std: float) -> float:
    if std <= 0:
        return 0.5
    z = (line + 0.5 - projection) / std
    return max(0.05, min(0.95, 1.0 - _norm_cdf(z)))


def _dk_line(projection: float) -> float:
    """Sportsbook-style half-point line near the average."""
    return round(projection * 2) / 2


def _confidence(edge: float, prob: float) -> str:
    if edge >= 0.06 and max(prob, 1 - prob) >= 0.57:
        return "HIGH"
    if edge >= 0.03 and max(prob, 1 - prob) >= 0.54:
        return "MEDIUM"
    if edge >= 0.01:
        return "LEAN"
    return "PASS"


def build_player_prop_picks(
    players: list[PlayerAverages],
    bankroll: float = 500.0,
    relaxed: bool = True,
) -> list[PropPick]:
    fair = american_to_implied(-110)
    picks: list[PropPick] = []

    for p in players:
        min_factor = min(1.05, max(0.95, p.min / 32.0))

        props_to_run: list[tuple[str, float, float]] = []
        for prop, field in PROP_FIELDS.items():
            avg = getattr(p, field)
            if avg <= 0:
                continue
            props_to_run.append((prop, avg * min_factor, PROP_STD[prop]))

        pra_proj = (p.pts + p.reb + p.ast) * min_factor
        props_to_run.append(("pts+reb+ast", pra_proj, PROP_STD["pts+reb+ast"]))

        for prop, projection, std in props_to_run:
            line = _dk_line(projection)
            p_over = prob_over(projection, line, std)
            p_under = 1.0 - p_over

            if p_over >= p_under:
                side, prob = "Over", p_over
            else:
                side, prob = "Under", p_under

            edge = prob - fair
            if not relaxed and edge < 0.02:
                continue
            conf = _confidence(edge, prob)
            if not relaxed and conf == "PASS":
                continue

            stake = kelly_stake(bankroll, prob, -110, fraction=0.15, max_pct=0.02)
            if stake <= 0 and relaxed:
                stake = 1.0

            picks.append(
                PropPick(
                    player=p.player,
                    team=p.team,
                    prop=prop,
                    line=line,
                    projection=round(projection, 1),
                    pick=side,
                    prob=prob,
                    edge=edge,
                    ev=expected_value(prob, -110),
                    stake=stake,
                    confidence=conf,
                )
            )

    conf_order = {"HIGH": 0, "MEDIUM": 1, "LEAN": 2, "PASS": 3}
    picks.sort(key=lambda x: (conf_order.get(x.confidence, 9), -x.edge))
    return picks


def props_for_fixture(
    match: str | None = None,
    date: str | None = None,
    bankroll: float = 500.0,
    relaxed: bool = True,
) -> tuple[dict, list[PropPick], pd.DataFrame]:
    event = find_event(match, date=date)
    players = load_fixture_players(event)
    picks = build_player_prop_picks(players, bankroll=bankroll, relaxed=relaxed)

    rows = [
        {
            "player": p.player,
            "team": p.team,
            "min": p.min,
            "pts": p.pts,
            "reb": p.reb,
            "ast": p.ast,
            "fg3m": p.fg3m,
            "stl": p.stl,
            "blk": p.blk,
            "pra": round(p.pts + p.reb + p.ast, 1),
        }
        for p in players
    ]
    df = pd.DataFrame(rows).sort_values("pts", ascending=False) if rows else pd.DataFrame()
    return event, picks, df
