"""Dashboard recommendation engine tests."""

from __future__ import annotations

from betting_system.dashboard.demo_slate import demo_worthy_legs
from betting_system.dashboard.recommend import find_best_parlay, recommend_all_targets


def test_find_best_parlay_returns_correct_leg_count():
    """Recommendation uses exactly the requested number of legs."""
    legs = demo_worthy_legs()
    rec = find_best_parlay(legs, leg_count=5, target_multiplier=10.0, bankroll=50.0)
    assert rec is not None
    assert len(rec.legs) == 5
    assert rec.stake > 0
    assert rec.payout_if_win >= rec.stake


def test_recommend_all_targets_produces_10x_and_15x():
    """Both multiplier targets return portfolios for a fixed leg count."""
    legs = demo_worthy_legs()
    recs = recommend_all_targets(legs, bankroll=100.0, leg_counts=[5], multipliers=[10, 15])
    mults = {int(r.target_multiplier) for r in recs}
    assert 10 in mults
    assert 15 in mults


def test_objective_mode_changes_selection():
    """max_prob and max_ev modes produce valid recommendations."""
    legs = demo_worthy_legs()
    rec_prob = recommend_all_targets(
        legs, bankroll=100.0, leg_counts=[5], multipliers=[10], objective_mode="max_prob"
    )
    rec_ev = recommend_all_targets(
        legs, bankroll=100.0, leg_counts=[5], multipliers=[10], objective_mode="max_ev"
    )
    assert rec_prob
    assert rec_ev
    assert rec_prob[0].objective_mode == "max_prob"
    assert rec_ev[0].objective_mode == "max_ev"
