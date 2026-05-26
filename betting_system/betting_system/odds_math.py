from __future__ import annotations


def american_to_decimal(odds_american: int) -> float:
    if odds_american == 0:
        raise ValueError("American odds cannot be 0")
    if odds_american > 0:
        return 1.0 + (odds_american / 100.0)
    return 1.0 + (100.0 / abs(odds_american))


def implied_prob_from_american(odds_american: int) -> float:
    dec = american_to_decimal(odds_american)
    return 1.0 / dec


def compute_ev_per_unit(p_hit: float, odds_american: int) -> float:
    dec = american_to_decimal(odds_american)
    # per-unit stake EV: win profit (dec-1) with p, lose 1 with (1-p)
    return (p_hit * (dec - 1.0)) - (1.0 - p_hit)

