"""Generate a deterministic synthetic prediction-market slate artifact.

This script is intentionally offline-only. It creates a small parquet file with
the minimal columns used by Edge Desk smoke tests and demos.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_OUT = Path("betting_system/data/processed/synthetic_prediction_markets.parquet")


def generate_synthetic_slate(*, out_path: str | Path = DEFAULT_OUT, seed: int = 42) -> Path:
    """Write a deterministic synthetic market slate and return its path."""
    rng = np.random.default_rng(seed)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    close_base = datetime.now(timezone.utc).date() + timedelta(days=30)
    venues = ["polymarket", "kalshi", "polymarket", "kalshi", "polymarket"]
    questions = [
        "Fed cuts rates at the next FOMC meeting?",
        "BTC closes above 150000 by year end?",
        "Brazil wins the 2026 FIFA World Cup?",
        "US CPI YoY below 2 percent in Q3?",
        "ETH closes above 10000 by year end?",
    ]
    mark_prices = np.array([0.54, 0.31, 0.18, 0.28, 0.12], dtype=float)
    model_edges = rng.normal(loc=0.035, scale=0.01, size=len(mark_prices))
    model_p_hit = np.clip(mark_prices + model_edges, 0.02, 0.98)
    df = pd.DataFrame(
        {
            "market_id": [f"synthetic-{i + 1}" for i in range(len(mark_prices))],
            "question": questions,
            "mark_price": mark_prices,
            "model_p_hit": model_p_hit,
            "venue": venues,
            "close_date": [
                (close_base + timedelta(days=idx * 14)).isoformat()
                for idx in range(len(mark_prices))
            ],
        }
    )
    df.to_parquet(out, index=False)
    return out


def main() -> None:
    """CLI entrypoint for synthetic slate generation."""
    parser = argparse.ArgumentParser(description="Generate a deterministic synthetic market slate")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output parquet path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    out = generate_synthetic_slate(out_path=args.out, seed=args.seed)
    print(out)


if __name__ == "__main__":
    main()
