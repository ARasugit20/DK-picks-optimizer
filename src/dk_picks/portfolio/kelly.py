def kelly_stake(
    bankroll: float,
    prob_win: float,
    american: int,
    fraction: float = 0.25,
    max_pct: float = 0.05,
) -> float:
    """Fractional Kelly stake capped at max_pct of bankroll."""
    if american > 0:
        b = american / 100
    else:
        b = 100 / abs(american)
    q = 1 - prob_win
    kelly = (b * prob_win - q) / b if b > 0 else 0.0
    kelly = max(0.0, kelly) * fraction
    stake = bankroll * kelly
    cap = bankroll * max_pct
    return round(min(stake, cap), 2)
