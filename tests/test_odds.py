from dk_picks.odds import american_to_implied, devig_two_way, expected_value, parlay_joint_prob


def test_american_to_implied():
    assert abs(american_to_implied(-110) - 0.5238) < 0.01
    assert abs(american_to_implied(150) - 0.4) < 0.01


def test_devig():
    a, b = devig_two_way(0.55, 0.55)
    assert abs(a + b - 1.0) < 1e-6


def test_parlay_joint():
    j = parlay_joint_prob([0.6, 0.6], correlation_penalty=0.1)
    assert j < 0.36


def test_ev_positive():
    ev = expected_value(0.55, -110)
    assert ev > 0
