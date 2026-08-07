"""Property-based invariants for parlay correlation discount math."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from betting_system.optimizer.parlay_builder import pairwise_correlation_discount
from dk_picks.odds import parlay_joint_prob


@given(st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False), min_size=0, max_size=8))
@settings(max_examples=100)
def test_pairwise_discount_bounded(correlations: list[float]):
    """Discount stays within [0, 1] for any valid correlation list."""
    discount = pairwise_correlation_discount(correlations)
    assert 0.0 <= discount <= 1.0 + 1e-9


@given(
    base=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False),
    extra=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=100)
def test_adding_correlated_pair_does_not_increase_discount(base: float, extra: float):
    """Adding another correlated leg never increases the discount multiplier."""
    before = pairwise_correlation_discount([base])
    after = pairwise_correlation_discount([base, extra])
    assert after <= before + 1e-9


def test_discount_symmetric_under_pair_ordering():
    """Pair ordering should not change the combined discount."""
    values = [0.2, -0.3, 0.15]
    forward = pairwise_correlation_discount(values)
    reverse = pairwise_correlation_discount(list(reversed(values)))
    assert math.isclose(forward, reverse, rel_tol=0.0, abs_tol=1e-9)


@given(st.floats(min_value=-0.99, max_value=0.99, allow_nan=False))
@settings(max_examples=50)
def test_discount_zero_only_when_fully_correlated(corr: float):
    """Discount reaches zero only when at least one |corr| == 1."""
    discount = pairwise_correlation_discount([corr])
    if abs(abs(corr) - 1.0) < 1e-9:
        assert discount == pytest.approx(0.0, abs=1e-9)
    else:
        assert discount > 0.0


def test_betting_system_discount_differs_from_dk_picks_joint_penalty():
    """Document intentional divergence between portfolio optimizers."""
    probs = [0.58, 0.57]
    betting_discount = pairwise_correlation_discount([0.12, 0.12])
    betting_joint = probs[0] * probs[1] * betting_discount
    legacy_joint = parlay_joint_prob(probs, correlation_penalty=0.12)
    assert betting_joint != pytest.approx(legacy_joint, rel=1e-6, abs=1e-6)
