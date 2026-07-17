from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from betting_system.config import load_settings


app = FastAPI(title="Probabilistic Forecasting & Portfolio API", version="0.1.0")


def _processed_path(name: str) -> Path:
    settings = load_settings()
    return Path(settings.data["processed_data_path"]) / name


@app.get("/picks/today")
def picks_today() -> Any:
    """Return today's prop forecasts and correlated multi-leg portfolios."""
    p = _processed_path("picks_today.json")
    if not p.exists():
        raise HTTPException(status_code=404, detail="No picks generated yet. Run pipeline first.")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/picks/{slate_id}")
def picks_by_slate(slate_id: str) -> Any:
    p = _processed_path(f"picks_{slate_id}.json")
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"No picks found for slate_id={slate_id}")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/model/calibration")
def model_calibration() -> Any:
    p = _processed_path("calibration_latest.json")
    if not p.exists():
        raise HTTPException(status_code=404, detail="No calibration metrics logged yet. Train model first.")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/bankroll")
def capital_allocation() -> Any:
    """Return current capital allocation state (bankroll, exposure, PnL)."""
    p = _processed_path("bankroll.json")
    if not p.exists():
        # default bankroll state
        return {"bankroll": 1000.0, "exposure": 0.0, "pnl": 0.0}
    return json.loads(p.read_text(encoding="utf-8"))


@app.post("/result")
def post_result(payload: dict[str, Any]) -> Any:
    # v1: append results for later retraining triggers
    p = _processed_path("submitted_results.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")
    return {"ok": True}


@app.get("/markets/opportunities")
def market_opportunities() -> Any:
    """Return ranked prediction-market opportunities with hero pick and metadata."""
    p = _processed_path("market_opportunities.json")
    if not p.exists():
        raise HTTPException(
            status_code=404,
            detail="No market opportunities yet. Run dk-market-pipeline first.",
        )
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/markets/portfolio")
def market_portfolio() -> Any:
    """Return open positions and account summary for prediction markets."""
    p = _processed_path("market_opportunities.json")
    if not p.exists():
        return {"portfolio": [], "account": {"equity": 0, "daily_edge_captured": 0, "open_pnl": 0}}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"portfolio": data.get("portfolio", []), "account": data.get("account", {})}


@app.get("/markets/{market_id}")
def market_detail(market_id: str) -> Any:
    """Return a single market opportunity by id."""
    p = _processed_path("market_opportunities.json")
    if not p.exists():
        raise HTTPException(status_code=404, detail="No market data available.")
    data = json.loads(p.read_text(encoding="utf-8"))
    for m in data.get("opportunities", []):
        if m.get("market_id") == market_id:
            return m
    hero = data.get("hero_pick")
    if hero and hero.get("market_id") == market_id:
        return hero
    raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")

