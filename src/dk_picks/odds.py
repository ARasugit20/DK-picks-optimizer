"""Convert American odds to probabilities and remove vig."""


def american_to_implied(american: int) -> float:
    if american > 0:
        return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)


def implied_to_american(prob: float) -> int:
    if prob <= 0 or prob >= 1:
        raise ValueError("prob must be in (0, 1)")
    if prob >= 0.5:
        return int(round(-100 * prob / (1 - prob)))
    return int(round(100 * (1 - prob) / prob))


def devig_two_way(prob_a: float, prob_b: float) -> tuple[float, float]:
    """Shin-style simple normalization for two-outcome markets."""
    total = prob_a + prob_b
    if total <= 0:
        return prob_a, prob_b
    return prob_a / total, prob_b / total


def parlay_joint_prob(probs: list[float], correlation_penalty: float = 0.0) -> float:
    """Independent joint with optional penalty per extra leg in same event."""
    if not probs:
        return 0.0
    joint = 1.0
    for p in probs:
        joint *= p
    joint *= max(0.0, 1.0 - correlation_penalty * max(0, len(probs) - 1))
    return min(max(joint, 0.0), 1.0)


def expected_value(prob_win: float, american: int) -> float:
    """EV per $1 staked."""
    if american > 0:
        profit = american / 100
    else:
        profit = 100 / abs(american)
    return prob_win * profit - (1 - prob_win)
