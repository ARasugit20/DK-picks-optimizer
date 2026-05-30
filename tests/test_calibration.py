"""Calibration quality tests (ECE on held-out probabilities)."""

from __future__ import annotations

import numpy as np

from betting_system.config import load_settings
from betting_system.pipeline.train import expected_calibration_error


def test_ece_below_config_threshold_on_well_calibrated_sample():
    """Synthetic near-perfect calibration should pass the configured ECE ceiling."""
    settings = load_settings()
    ece_max = float(settings.training["calibration"]["ece_test_max"])
    rng = np.random.default_rng(int(settings.model["random_seed"]))
    n = 2000
    y_prob = rng.uniform(0.35, 0.75, size=n)
    y_true = (rng.uniform(0, 1, size=n) < y_prob).astype(int)
    ece = expected_calibration_error(y_true, y_prob, n_bins=10)
    assert ece < ece_max
