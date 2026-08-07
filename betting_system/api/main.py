from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from betting_system.config import load_settings
from betting_system.logging_utils import get_logger, log_event
from betting_system.markets.edge_evaluation import evaluate_market_edges
from betting_system.markets.ledger import read_trades
from betting_system.markets.money_weighted import summarize_money_weighted_trades
from betting_system.schemas import (
    BankrollResponse,
    CalibrationMetricsResponse,
    EdgeSummaryResponse,
    HealthResponse,
    MarketOpportunitiesResponse,
    MarketOpportunity,
    MarketPortfolioResponse,
    ModelStatusResponse,
    PnlAttributionResponse,
    ResultPostResponse,
    SlatePicks,
)


logger = get_logger(__name__)
app = FastAPI(title="Probabilistic Forecasting & Portfolio API", version="0.1.0")


def _processed_path(name: str) -> Path:
    settings = load_settings()
    return Path(settings.data["processed_data_path"]) / name


def _latest_metrics_path() -> Path | None:
    settings = load_settings()
    models_dir = Path(settings.data["models_path"]) / "leg_model"
    metrics = sorted(models_dir.glob("metrics_*_v1_*.json"))
    return metrics[-1] if metrics else None


def _artifact_version() -> str | None:
    metrics_path = _latest_metrics_path()
    if not metrics_path or not metrics_path.exists():
        return None
    try:
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return metrics_path.name
    return str(payload.get("artifact_version") or payload.get("market_type") or metrics_path.name)


def _source_from_payload(payload: dict[str, Any], default: str = "fixture_fallback") -> str:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    if "data_source" in payload:
        return str(payload["data_source"])
    if "data_source" in meta:
        return str(meta["data_source"])
    if meta.get("is_live"):
        return "live"
    return default


def _with_data_source(payload: Any, *, default: str = "fixture_fallback") -> Any:
    if not isinstance(payload, dict):
        return payload
    data_source = _source_from_payload(payload, default=default)
    enriched = {**payload, "data_source": data_source}
    if isinstance(enriched.get("hero_pick"), dict):
        enriched["hero_pick"] = {**enriched["hero_pick"], "data_source": data_source}
    if isinstance(enriched.get("opportunities"), list):
        enriched["opportunities"] = [
            {**item, "data_source": data_source} if isinstance(item, dict) else item
            for item in enriched["opportunities"]
        ]
    return enriched


def _validate_artifact(model: type[BaseModel], payload: Any, *, artifact: str) -> BaseModel:
    """Validate enriched artifact payloads and fail loudly at the API boundary."""
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        logger.error("Invalid %s artifact: %s", artifact, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Invalid {artifact} artifact: {exc.errors()}",
        ) from exc


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach request IDs and emit structured latency logs."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(
            logger,
            "http_request",
            request_id=request_id,
            method=request.method,
            route=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
            artifact_version=_artifact_version(),
        )
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestLoggingMiddleware)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return lightweight service health and artifact availability."""
    settings = load_settings()
    processed = Path(settings.data["processed_data_path"])
    return HealthResponse(
        status="ok",
        service="edge-desk-api",
        processed_path=str(processed),
        picks_today_exists=_processed_path("picks_today.json").exists(),
        market_opportunities_exists=_processed_path("market_opportunities.json").exists(),
        config_valid=True,
    )


@app.get("/model/status", response_model=ModelStatusResponse)
def model_status() -> ModelStatusResponse:
    """Return model artifact and validation metadata availability."""
    model_path = _processed_path("models/model.pkl")
    metrics_path = _latest_metrics_path()
    metrics = None
    if metrics_path and metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    return ModelStatusResponse(
        model_available=model_path.exists(),
        model_path=str(model_path),
        metrics_available=metrics is not None,
        metrics_path=str(metrics_path) if metrics_path else None,
        metrics=metrics,
    )


@app.get("/picks/today", response_model=SlatePicks)
def picks_today() -> SlatePicks:
    """Return today's prop forecasts and correlated multi-leg portfolios."""
    p = _processed_path("picks_today.json")
    if not p.exists():
        raise HTTPException(status_code=404, detail="No picks generated yet. Run pipeline first.")
    payload = _with_data_source(json.loads(p.read_text(encoding="utf-8")))
    return _validate_artifact(SlatePicks, payload, artifact="picks_today")


@app.get("/picks/{slate_id}", response_model=SlatePicks)
def picks_by_slate(slate_id: str) -> SlatePicks:
    p = _processed_path(f"picks_{slate_id}.json")
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"No picks found for slate_id={slate_id}")
    payload = _with_data_source(json.loads(p.read_text(encoding="utf-8")))
    return _validate_artifact(SlatePicks, payload, artifact=f"picks_{slate_id}")


@app.get("/model/calibration", response_model=CalibrationMetricsResponse)
def model_calibration() -> CalibrationMetricsResponse:
    p = _processed_path("calibration_latest.json")
    if not p.exists():
        raise HTTPException(status_code=404, detail="No calibration metrics logged yet. Train model first.")
    payload = _with_data_source(json.loads(p.read_text(encoding="utf-8")))
    return _validate_artifact(CalibrationMetricsResponse, payload, artifact="calibration_latest")


@app.get("/bankroll", response_model=BankrollResponse)
def capital_allocation() -> BankrollResponse:
    """Return current capital allocation state (bankroll, exposure, PnL)."""
    p = _processed_path("bankroll.json")
    if not p.exists():
        return BankrollResponse(bankroll=1000.0, exposure=0.0, pnl=0.0)
    payload = json.loads(p.read_text(encoding="utf-8"))
    return _validate_artifact(BankrollResponse, payload, artifact="bankroll")


@app.post("/result", response_model=ResultPostResponse)
def post_result(payload: dict[str, Any]) -> ResultPostResponse:
    # v1: append results for later retraining triggers
    p = _processed_path("submitted_results.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")
    return ResultPostResponse(ok=True)


@app.get("/markets/opportunities", response_model=MarketOpportunitiesResponse)
def market_opportunities() -> MarketOpportunitiesResponse:
    """Return ranked prediction-market opportunities with hero pick and metadata."""
    p = _processed_path("market_opportunities.json")
    if not p.exists():
        raise HTTPException(
            status_code=404,
            detail="No market opportunities yet. Run dk-market-pipeline first.",
        )
    payload = _with_data_source(json.loads(p.read_text(encoding="utf-8")))
    return _validate_artifact(MarketOpportunitiesResponse, payload, artifact="market_opportunities")


@app.get("/markets/portfolio", response_model=MarketPortfolioResponse)
def market_portfolio() -> MarketPortfolioResponse:
    """Return open positions and account summary for prediction markets."""
    p = _processed_path("market_opportunities.json")
    if not p.exists():
        return MarketPortfolioResponse(
            data_source="fixture_fallback",
            portfolio=[],
            account={"equity": 0, "daily_edge_captured": 0, "open_pnl": 0},
        )
    data = _with_data_source(json.loads(p.read_text(encoding="utf-8")))
    response_payload = {
        "data_source": data.get("data_source", "fixture_fallback"),
        "portfolio": data.get("portfolio", []),
        "account": data.get("account", {}),
    }
    return _validate_artifact(MarketPortfolioResponse, response_payload, artifact="market_portfolio")


@app.get("/markets/edge-summary", response_model=EdgeSummaryResponse)
def market_edge_summary() -> EdgeSummaryResponse:
    """Return Edge Desk outcome-validation summary for logged market edges."""
    return EdgeSummaryResponse.model_validate(evaluate_market_edges().to_dict())


@app.get("/markets/pnl-attribution", response_model=PnlAttributionResponse)
def market_pnl_attribution() -> PnlAttributionResponse:
    """Return money-weighted PnL and calibration attribution for market trades."""
    trades = read_trades()
    summary = summarize_money_weighted_trades(trades)
    payload = {
        "trade_count": len(trades),
        "money_weighted": summary.to_dict(),
    }
    return _validate_artifact(PnlAttributionResponse, payload, artifact="market_pnl_attribution")


@app.get("/markets/{market_id}", response_model=MarketOpportunity)
def market_detail(market_id: str) -> MarketOpportunity:
    """Return a single market opportunity by id."""
    p = _processed_path("market_opportunities.json")
    if not p.exists():
        raise HTTPException(status_code=404, detail="No market data available.")
    data = _with_data_source(json.loads(p.read_text(encoding="utf-8")))
    for market in data.get("opportunities", []):
        if market.get("market_id") == market_id:
            return _validate_artifact(MarketOpportunity, market, artifact=f"market:{market_id}")
    hero = data.get("hero_pick")
    if hero and hero.get("market_id") == market_id:
        return _validate_artifact(MarketOpportunity, hero, artifact=f"market:{market_id}")
    raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
