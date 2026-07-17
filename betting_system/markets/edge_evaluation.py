"""Durable Edge Desk edge logs and outcome evaluation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any

from betting_system.config import load_settings
from betting_system.markets.base import ForecastMarket


def _processed_dir() -> Path:
    return Path(load_settings().data["processed_data_path"])


def edge_log_path(out_dir: Path | None = None) -> Path:
    """Return the durable market edge log path."""
    return (out_dir or _processed_dir()) / "market_edge_log.jsonl"


def edge_resolution_path(out_dir: Path | None = None) -> Path:
    """Return the durable market resolution log path."""
    return (out_dir or _processed_dir()) / "market_edge_resolutions.jsonl"


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, default=str) + "\n")


def record_market_edge_snapshot(
    opportunities: list[ForecastMarket],
    *,
    data_source: str,
    run_id: str,
    out_dir: Path | None = None,
) -> Path:
    """Persist fair-value probabilities so future settlements can be audited."""
    path = edge_log_path(out_dir)
    recorded_at = datetime.now(timezone.utc).isoformat()
    for market in opportunities:
        _append_jsonl(
            path,
            {
                "run_id": run_id,
                "recorded_at": recorded_at,
                "market_id": market.market_id,
                "event_id": market.event_id,
                "venue": market.venue,
                "category": market.category,
                "question": market.question,
                "outcome": market.outcome,
                "market_price": market.market_price,
                "fair_value_prob": market.fair_price,
                "edge": market.edge,
                "data_source": data_source,
            },
        )
    return path


def record_market_resolution(
    *,
    market_id: str,
    realized: bool,
    resolved_at: datetime | None = None,
    source: str = "manual",
    out_dir: Path | None = None,
) -> Path:
    """Append a settled outcome for a previously logged market edge."""
    path = edge_resolution_path(out_dir)
    _append_jsonl(
        path,
        {
            "market_id": market_id,
            "realized": bool(realized),
            "resolved_at": (resolved_at or datetime.now(timezone.utc)).isoformat(),
            "source": source,
        },
    )
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def expected_calibration_error(
    outcomes: list[float],
    probabilities: list[float],
    *,
    n_bins: int = 10,
) -> float | None:
    """Compute market-layer expected calibration error."""
    if not outcomes:
        return None
    total = len(outcomes)
    ece = 0.0
    for bin_idx in range(n_bins):
        lo = bin_idx / n_bins
        hi = (bin_idx + 1) / n_bins
        idx = [
            i
            for i, prob in enumerate(probabilities)
            if (lo <= prob < hi) or (bin_idx == n_bins - 1 and prob == 1.0)
        ]
        if not idx:
            continue
        avg_outcome = sum(outcomes[i] for i in idx) / len(idx)
        avg_prob = sum(probabilities[i] for i in idx) / len(idx)
        ece += (len(idx) / total) * abs(avg_outcome - avg_prob)
    return ece


@dataclass(frozen=True)
class EdgeSummary:
    """Resolved Edge Desk evaluation metrics."""

    logged_edges: int
    resolved_edges: int
    mean_edge: float | None
    mean_edge_realized: float | None
    brier: float | None
    ece: float | None
    t_stat_edge_vs_zero: float | None
    p_value_edge_vs_zero_approx: float | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize summary for API/dashboard payloads."""
        return {
            "logged_edges": self.logged_edges,
            "resolved_edges": self.resolved_edges,
            "mean_edge": self.mean_edge,
            "mean_edge_realized": self.mean_edge_realized,
            "brier": self.brier,
            "ece": self.ece,
            "t_stat_edge_vs_zero": self.t_stat_edge_vs_zero,
            "p_value_edge_vs_zero_approx": self.p_value_edge_vs_zero_approx,
            "status": self.status,
        }


def evaluate_market_edges(*, out_dir: Path | None = None) -> EdgeSummary:
    """Evaluate logged fair-value edges against settled market outcomes."""
    out_dir = out_dir or _processed_dir()
    edge_rows = _read_jsonl(edge_log_path(out_dir))
    resolution_rows = _read_jsonl(edge_resolution_path(out_dir))
    latest_resolution = {row["market_id"]: row for row in resolution_rows}

    resolved = [
        (edge, latest_resolution[edge["market_id"]])
        for edge in edge_rows
        if edge.get("market_id") in latest_resolution
    ]
    logged_count = len(edge_rows)
    if not resolved:
        return EdgeSummary(
            logged_edges=logged_count,
            resolved_edges=0,
            mean_edge=None,
            mean_edge_realized=None,
            brier=None,
            ece=None,
            t_stat_edge_vs_zero=None,
            p_value_edge_vs_zero_approx=None,
            status="pending_resolutions" if logged_count else "no_edge_log",
        )

    probs = [float(edge["fair_value_prob"]) for edge, _ in resolved]
    market_prices = [float(edge["market_price"]) for edge, _ in resolved]
    outcomes = [1.0 if bool(res["realized"]) else 0.0 for _, res in resolved]
    edges = [prob - market for prob, market in zip(probs, market_prices, strict=True)]
    realized_edges = [outcome - market for outcome, market in zip(outcomes, market_prices, strict=True)]

    brier = sum((prob - outcome) ** 2 for prob, outcome in zip(probs, outcomes, strict=True)) / len(probs)
    ece = expected_calibration_error(outcomes, probs)
    mean_edge = sum(edges) / len(edges)
    mean_realized = sum(realized_edges) / len(realized_edges)

    t_stat = None
    p_value = None
    if len(realized_edges) > 1:
        variance = sum((value - mean_realized) ** 2 for value in realized_edges) / (len(realized_edges) - 1)
        stderr = math.sqrt(variance / len(realized_edges)) if variance > 0 else 0.0
        if stderr > 0:
            t_stat = mean_realized / stderr
            p_value = 2 * (1 - NormalDist().cdf(abs(t_stat)))

    return EdgeSummary(
        logged_edges=logged_count,
        resolved_edges=len(resolved),
        mean_edge=mean_edge,
        mean_edge_realized=mean_realized,
        brier=brier,
        ece=ece,
        t_stat_edge_vs_zero=t_stat,
        p_value_edge_vs_zero_approx=p_value,
        status="resolved",
    )
