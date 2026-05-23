from dataclasses import dataclass
from itertools import combinations

import pandas as pd

from dk_picks.config import load_thresholds
from dk_picks.odds import american_to_implied, parlay_joint_prob
from dk_picks.portfolio.kelly import kelly_stake


@dataclass
class Leg:
    event_id: str
    outcome: str
    model_prob: float
    fair_prob: float
    edge: float
    price_american: int
    home_team: str
    away_team: str


def rank_singles(df: pd.DataFrame, bankroll: float) -> pd.DataFrame:
    t = load_thresholds()
    edge_cfg = t.get("edge", {})
    bank_cfg = t.get("bankroll", {})
    min_edge = edge_cfg.get("min_single_edge", 0.03)
    min_conf = edge_cfg.get("min_model_confidence", 0.58)

    filtered = df[(df["edge"] >= min_edge) & (df["model_prob"] >= min_conf)].copy()
    filtered["stake"] = filtered.apply(
        lambda r: kelly_stake(
            bankroll,
            r["model_prob"],
            int(r["price_american"]),
            fraction=bank_cfg.get("kelly_fraction", 0.25),
            max_pct=bank_cfg.get("max_bet_pct", 0.05),
        ),
        axis=1,
    )
    return filtered.sort_values("ev", ascending=False)


def _same_game_penalty(legs: list[Leg], penalty: float) -> float:
    events = [leg.event_id for leg in legs]
    extra = len(events) - len(set(events))
    return penalty * max(0, extra)


def build_parlay_slips(df: pd.DataFrame, bankroll: float, max_parlays: int = 10) -> list[dict]:
    t = load_thresholds()
    p_cfg = t.get("parlay", {})
    e_cfg = t.get("edge", {})
    b_cfg = t.get("bankroll", {})

    min_edge = e_cfg.get("min_parlay_edge", 0.05)
    max_legs = p_cfg.get("max_legs", 3)
    corr_pen = p_cfg.get("correlation_penalty", 0.12)
    max_same_game = p_cfg.get("max_same_game_legs", 1)

    candidates = df[df["edge"] >= e_cfg.get("min_single_edge", 0.03)].head(40)
    legs = [
        Leg(
            event_id=r.event_id,
            outcome=r.outcome,
            model_prob=r.model_prob,
            fair_prob=r.fair_prob,
            edge=r.edge,
            price_american=int(r.price_american),
            home_team=r.home_team,
            away_team=r.away_team,
        )
        for r in candidates.itertuples()
    ]

    parlays = []
    for size in range(2, max_legs + 1):
        for combo in combinations(legs, size):
            event_ids = [leg.event_id for leg in combo]
            if max(event_ids.count(e) for e in set(event_ids)) > max_same_game:
                continue

            probs = [leg.model_prob for leg in combo]
            penalty = _same_game_penalty(list(combo), corr_pen)
            joint_p = parlay_joint_prob(probs, correlation_penalty=penalty)

            fair_joint = 1.0
            for leg in combo:
                fair_joint *= leg.fair_prob
            edge = joint_p - fair_joint
            if edge < min_edge or joint_p < e_cfg.get("min_model_confidence", 0.58):
                continue

            # Approximate parlay American odds from leg prices (independent)
            dec = 1.0
            for leg in combo:
                imp = american_to_implied(leg.price_american)
                dec *= 1 / imp if imp > 0 else 1
            parlay_american = int(round((dec - 1) * 100)) if dec >= 2 else -110

            stake = kelly_stake(
                bankroll,
                joint_p,
                parlay_american,
                fraction=b_cfg.get("kelly_fraction", 0.25) * 0.5,
                max_pct=b_cfg.get("max_bet_pct", 0.05) * 0.8,
            )
            if stake <= 0:
                continue

            parlays.append(
                {
                    "legs": [f"{leg.outcome} ({leg.away_team} @ {leg.home_team})" for leg in combo],
                    "joint_prob": round(joint_p, 4),
                    "edge": round(edge, 4),
                    "stake": stake,
                    "approx_odds": parlay_american,
                }
            )

    parlays.sort(key=lambda x: x["edge"], reverse=True)
    return parlays[:max_parlays]
