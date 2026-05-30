#!/usr/bin/env python3
"""Plot reliability diagram from holdout calibration sample and save to docs/."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betting_system.config import load_settings


def load_holdout_probs(csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load binary outcomes and predicted probabilities from CSV."""
    df = pd.read_csv(csv_path)
    return df["y_true"].to_numpy(dtype=int), df["y_prob"].to_numpy(dtype=float)


def plot_reliability_diagram(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    n_bins: int,
    out_path: Path,
) -> None:
    """Save reliability diagram (predicted vs observed frequency) to *out_path*."""
    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="uniform")
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect calibration")
    ax.plot(prob_pred, prob_true, marker="o", label="Model")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title("Reliability diagram (holdout)")
    ax.legend(loc="lower right")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> None:
    """Entry point: read fixture, plot, write docs/calibration_plot.png."""
    settings = load_settings()
    n_bins = int(settings.training["calibration"].get("calibration_plot_bins", 10))
    csv_path = ROOT / "betting_system" / "data" / "fixtures" / "calibration_holdout.csv"
    out_path = ROOT / "docs" / "calibration_plot.png"
    y_true, y_prob = load_holdout_probs(csv_path)
    plot_reliability_diagram(y_true, y_prob, n_bins=n_bins, out_path=out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
