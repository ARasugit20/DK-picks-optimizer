"""FIFA World Cup 2026 market adapter and score modeling."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import poisson

from betting_system.logging_utils import get_logger


logger = get_logger(__name__)


def ingest_wc_matches(*, fixture_path: str | Path | None = None) -> pd.DataFrame:
    """Load World Cup match results from fixture or future API."""
    if fixture_path is None:
        fixture_path = Path(__file__).resolve().parent / "data" / "wc_matches_fixture.csv"
    p = Path(fixture_path)
    if not p.exists():
        return _generate_wc_fixture()
    return pd.read_csv(p)


def _generate_wc_fixture() -> pd.DataFrame:
    """Synthetic WC matches for development (2018/2022 style)."""
    rows = [
        {"match_id": "wc2018_1", "date": "2018-06-14", "home_team": "RUS", "away_team": "KSA", "home_goals": 5, "away_goals": 0, "tournament": "2018"},
        {"match_id": "wc2018_2", "date": "2018-06-15", "home_team": "POR", "away_team": "ESP", "home_goals": 3, "away_goals": 3, "tournament": "2018"},
        {"match_id": "wc2022_1", "date": "2022-11-20", "home_team": "QAT", "away_team": "ECU", "home_goals": 0, "away_goals": 2, "tournament": "2022"},
        {"match_id": "wc2022_2", "date": "2022-11-21", "home_team": "ENG", "away_team": "IRN", "home_goals": 6, "away_goals": 2, "tournament": "2022"},
    ]
    return pd.DataFrame(rows)


def build_wc_features(matches: pd.DataFrame) -> pd.DataFrame:
    """Build team form features for World Cup matches."""
    df = matches.sort_values("date").copy()
    records = []
    for team in pd.unique(df[["home_team", "away_team"]].values.ravel()):
        team_matches = []
        for _, m in df.iterrows():
            if m["home_team"] == team:
                gf, ga = m["home_goals"], m["away_goals"]
            elif m["away_team"] == team:
                gf, ga = m["away_goals"], m["home_goals"]
            else:
                continue
            team_matches.append({"team": team, "date": m["date"], "gf": gf, "ga": ga})
        tdf = pd.DataFrame(team_matches).sort_values("date")
        tdf["gf_roll_5"] = tdf["gf"].shift(1).rolling(5, min_periods=1).mean()
        tdf["ga_roll_5"] = tdf["ga"].shift(1).rolling(5, min_periods=1).mean()
        records.append(tdf)
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def poisson_score_matrix(home_xg: float, away_xg: float, max_goals: int = 5) -> np.ndarray:
    """Return probability matrix P(home=i, away=j) under independent Poisson."""
    mat = np.zeros((max_goals + 1, max_goals + 1))
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            mat[i, j] = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
    return mat / mat.sum()


def derived_market_probs(score_mat: np.ndarray) -> dict[str, float]:
    """Derive 1X2, over 2.5, and BTTS from score probability matrix."""
    home_win = float(np.tril(score_mat, k=-1).sum())
    draw = float(np.trace(score_mat))
    away_win = float(np.triu(score_mat, k=1).sum())
    over_25 = float(sum(score_mat[i, j] for i in range(score_mat.shape[0]) for j in range(score_mat.shape[1]) if i + j > 2.5))
    btts = float(sum(score_mat[i, j] for i in range(1, score_mat.shape[0]) for j in range(1, score_mat.shape[1])))
    return {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "over_2_5": over_25,
        "btts_yes": btts,
    }


def forecast_match(home_xg: float, away_xg: float) -> dict[str, float]:
    """Full match forecast: score matrix and derived market probabilities."""
    mat = poisson_score_matrix(home_xg, away_xg)
    probs = derived_market_probs(mat)
    probs["home_xg"] = home_xg
    probs["away_xg"] = away_xg
    return probs
