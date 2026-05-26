from betting_system.odds_math import american_to_decimal, compute_ev_per_unit, implied_prob_from_american


def test_american_to_decimal_positive():
    assert american_to_decimal(100) == 2.0
    assert american_to_decimal(200) == 3.0


def test_american_to_decimal_negative():
    assert round(american_to_decimal(-110), 6) == round(1.0 + 100.0 / 110.0, 6)


def test_implied_prob():
    assert implied_prob_from_american(100) == 0.5


def test_ev_per_unit_break_even():
    # fair coin at +100 has 0 EV
    assert abs(compute_ev_per_unit(0.5, 100)) < 1e-9

