from __future__ import annotations

from betting_system.config import load_settings
from betting_system.odds_math import american_to_decimal, compute_ev_per_unit
from betting_system.schemas import EdgeResult


def compute_edge(p_hit: float, odds_american: int, *, min_edge: float | None = None, require_positive_ev: bool | None = None) -> EdgeResult:
    """Compare model p_hit to market-implied probability and flag worthy legs."""
    settings = load_settings()
    cfg = settings.model
    min_edge = cfg["min_edge"] if min_edge is None else min_edge
    require_positive_ev = cfg["worthy_requires_positive_ev"] if require_positive_ev is None else require_positive_ev

    dec = american_to_decimal(odds_american)
    p_market = 1.0 / dec  # includes vig; devig is a later enhancement
    ev = compute_ev_per_unit(p_hit, odds_american)
    edge = p_hit - p_market
    worthy = (edge > float(min_edge)) and ((ev > 0) if require_positive_ev else True)
    return EdgeResult(p_hit=p_hit, p_market=p_market, edge=edge, ev_per_unit=ev, worthy=worthy)

