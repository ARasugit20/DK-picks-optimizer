"""Demo slate data tests."""

from __future__ import annotations

from betting_system.dashboard.demo_slate import demo_worthy_legs


def test_demo_slate_has_enough_legs_for_15_leg_parlays():
    """Demo pool must support max dashboard leg count."""
    legs = demo_worthy_legs()
    assert len(legs) >= 15
    assert all("player_name" in leg for leg in legs)
    assert all("line" in leg for leg in legs)
