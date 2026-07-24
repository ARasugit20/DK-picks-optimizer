# System Design

## Purpose

Edge Desk is a probability-to-capital engine for uncertain event markets. It estimates fair probability, compares that probability with executable market prices, applies risk constraints, records the decision, and audits realized money-weighted outcomes after settlement.

## Goals

- Produce calibrated probabilities for sports props and prediction-market event contracts.
- Separate model probability from tradable execution price.
- Enforce capital, correlation, and exposure limits before a recommendation is surfaced.
- Preserve an audit trail from forecast to settlement.
- Run offline with fixtures for CI and live with external APIs when credentials are available.

## Non-Goals

- Automated real-money trading.
- Claiming live profitability from fixture data.
- Replacing venue-specific compliance or order-management systems.

## Data Flow

```text
market/stat source
  -> ingest
  -> normalize
  -> feature/scoring layer
  -> calibrated fair probability
  -> order-book / market-price comparison
  -> optimizer and exposure checks
  -> JSON artifacts
  -> FastAPI + Streamlit
  -> ledger / resolution logs
  -> calibration, PnL, and audit summaries
```

## Core Components

| Component | Responsibility |
|-----------|----------------|
| `betting_system/pipeline/` | Ingest, feature generation, model training, slate prediction, market pipeline orchestration |
| `betting_system/markets/` | Event contract schemas, fair-value scoring, order-book execution, trade ledger, money-weighted metrics |
| `betting_system/optimizer/` | Parlay construction, correlation discounting, Kelly/exposure caps |
| `betting_system/api/` | Artifact-backed HTTP surface for picks, markets, health, and attribution |
| `betting_system/dashboard/` | Streamlit terminal and model-health views |
| `docs/evidence/` | Versioned evidence artifacts when results are intentionally published |

## API Contracts

Primary read endpoints:

- `GET /health`
- `GET /model/status`
- `GET /picks/today`
- `GET /markets/opportunities`
- `GET /markets/edge-summary`
- `GET /markets/pnl-attribution`

All market-facing responses should expose `data_source` so live, fixture fallback, and synthetic artifacts are not confused.

## Model Lifecycle

1. Load validated config from `betting_system/config.yaml`.
2. Build leakage-safe features with shifted rolling windows.
3. Train model artifacts using time-aware validation.
4. Calibrate probabilities and record metrics.
5. Promote only when validation artifacts are archived.
6. Serve the latest blessed artifact with model status metadata.

## Reliability Model

Failure modes and expected behavior:

- Missing external API credentials: use fixture fallback where supported.
- Missing picks artifact: API returns 404 with runbook guidance.
- Missing model artifact: model status reports unavailable rather than crashing.
- Bad config: `dk-picks validate-config` exits nonzero before runtime.
- Empty settlement ledger: attribution endpoint returns pending metrics.

## Scaling Path

- Move processed artifacts to object storage.
- Move trade/edge ledgers to Postgres.
- Add async ingest workers for venue APIs.
- Cache market opportunities in Redis.
- Serve FastAPI horizontally with immutable model artifact versions.
- Keep training and backtesting offline from request/response serving.

## Security and Compliance

- Secrets live in environment variables, never in committed config.
- Artifacts must label data provenance.
- Live trading is out of scope unless a separate approval, custody, and compliance layer exists.
- Prediction outputs are decision support, not financial advice.
