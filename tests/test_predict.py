"""Edge and EV computation tests."""

from __future__ import annotations

from betting_system.pipeline.predict import compute_edge


def test_compute_edge_flags_worthy_when_above_min_edge():
    """Legs with sufficient model edge vs market-implied probability are worthy."""
    result = compute_edge(0.62, -110, min_edge=0.02, require_positive_ev=True)
    assert result.worthy
    assert result.edge > 0


def test_compute_edge_rejects_low_edge():
    """Legs below min_edge are not worthy."""
    result = compute_edge(0.51, -110, min_edge=0.10, require_positive_ev=True)
    assert not result.worthy
