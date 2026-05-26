from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from betting_system.config import load_settings
from betting_system.logging_utils import utcnow
from betting_system.schemas import ParlayPick, PickLeg, SlatePicks
from betting_system.optimizer.parlay_builder import build_parlay_candidates
from betting_system.optimizer.staking import parlay_stake_cap


def optimize_slate(
    *,
    slate_id: str,
    worthy_legs: list[dict[str, Any]],
    bankroll: float,
    corr_path: str | Path | None = None,
) -> SlatePicks:
    settings = load_settings()
    cfg = settings.model
    max_parlays = int(cfg["max_parlays_per_slate"])
    max_slate_exposure_pct = float(cfg["max_slate_exposure"])
    min_p_hit = float(cfg["min_p_hit"])

    # Hard filters
    filtered = []
    for leg in worthy_legs:
        if float(leg["p_hit"]) < min_p_hit:
            continue
        filtered.append(leg)

    candidates = build_parlay_candidates(filtered, corr_path=corr_path)

    picks: list[ParlayPick] = []
    exposure_cap = bankroll * max_slate_exposure_pct
    total_exposure = 0.0
    parlay_cap = parlay_stake_cap(bankroll=bankroll)

    for c in candidates:
        if len(picks) >= max_parlays:
            break
        if c["ev_per_unit"] <= 0:
            break
        if total_exposure + parlay_cap > exposure_cap:
            break

        parlay_id = str(uuid.uuid4())
        legs = [
            PickLeg(
                game_id=str(l["game_id"]),
                market_type=str(l["market_type"]),
                player_id=str(l["player_id"]),
                line=float(l["line"]),
                odds_american=int(l["odds_american"]),
                p_hit=float(l["p_hit"]),
                edge=float(l["edge"]),
                ev_per_unit=float(l["ev_per_unit"]),
            )
            for l in c["legs"]
        ]
        stake = float(parlay_cap)
        expected_payout = stake * float(c["decimal_odds"])
        picks.append(
            ParlayPick(
                parlay_id=parlay_id,
                legs=legs,
                p_parlay=float(c["p_parlay"]),
                ev_per_unit=float(c["ev_per_unit"]),
                stake=stake,
                expected_payout=expected_payout,
            )
        )
        total_exposure += stake

    return SlatePicks(
        slate_id=slate_id,
        generated_at=utcnow(),
        bankroll=float(bankroll),
        total_exposure=float(total_exposure),
        parlays=picks,
    )

