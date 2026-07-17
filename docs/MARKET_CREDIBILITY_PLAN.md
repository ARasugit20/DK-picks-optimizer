# Market Credibility Improvement Plan

## Objective

Position DK-Picks-Optimizer as a recruiter-ready forecasting and allocation system for prediction-market work. The project should stay honest about what is proven today, while making it easy for a Kalshi, Polymarket, or quant hiring team to verify calibration, leakage control, risk sizing, live-vs-fixture provenance, and Edge Desk market-edge outcomes.

## The Real Gap

The codebase already has the core technical pieces:

- LightGBM with isotonic calibration and sigmoid fallback by ECE threshold
- Walk-forward backtest machinery
- Fixture and live-style market pipelines
- FastAPI and Streamlit surfaces
- Kelly sizing with exposure and correlation constraints
- Edge Desk market fair-value scoring, curation, and durable edge logs
- Tests for leakage, calibration, API schemas, markets, optimizer behavior, and edge evaluation

The remaining gap is evidence, not model architecture. Recruiters should not have to infer whether README numbers are demo data, whether market rows are live or fixture fallback, or how sports-prop logic maps to binary event markets.

## Phase 1: Default-Branch Visibility

Status: in progress.

Actions:

- Merge `feat/edge-desk-terminal` into `main` so GitHub's default page shows the current Edge Desk positioning.
- Keep sports props as the proof domain, but describe the system as a market-agnostic probability and allocation engine.
- Keep the README backtest section explicit that the displayed table is synthetic until replaced by archived walk-forward logs.
- Link [PRODUCTION_EVIDENCE.md](PRODUCTION_EVIDENCE.md) wherever performance claims appear.

Why it matters: a stale default branch makes the project look unfinished even when the feature branch has the stronger story.

## Phase 2: Sports-Prop Proof Trail

Status: partially complete.

Artifacts already present:

- [PRODUCTION_EVIDENCE.md](PRODUCTION_EVIDENCE.md)
- [calibration_plot.png](calibration_plot.png)
- `betting_system/pipeline/backtest.py`
- `betting_system/pipeline/run_pipeline.py`

Next actions:

- Add a committed sample summary generated from a real or clearly labeled fixture run.
- Keep generated model/data artifacts out of Git unless they are intentionally small, documented evidence files.
- Replace the synthetic README table only after the source artifact is archived under `docs/evidence/`.

Runbook:

```bash
export PYTHONPATH="$(pwd)"
dk-pipeline --dry-run
python scripts/plot_calibration.py
```

Production runs require live API credentials and should preserve metadata showing whether each output came from live data or fixture fallback.

## Phase 3: Edge Desk Market-Edge Audit

Status: instrumented; pending settled live outcomes.

Current implementation:

- `betting_system/markets/edge_evaluation.py` logs market fair-value snapshots and evaluates settled outcomes.
- `betting_system/pipeline/run_market_pipeline.py` writes `market_edge_log.jsonl` alongside `market_opportunities.json`.
- `GET /markets/edge-summary` reports logged count, resolved count, Brier, ECE, mean realized edge, and an approximate edge-vs-zero test.
- The Streamlit top strip surfaces live/fixture provenance and edge-audit status.

Next actions:

- Append real Kalshi/Polymarket settlement outcomes to `market_edge_resolutions.jsonl`.
- Archive a settled live run under `docs/evidence/edge_desk_<date>/`.
- Link the archived summary from README once it is based on settled live contracts, not fixtures.

## Phase 4: Prediction-Market Case Study

Status: planned.

Create `docs/PREDICTION_MARKET_CASE_STUDY.md` with these sections:

- How a Kalshi binary event maps to the current `ForecastMarket` / market opportunity schema
- How fair probability is compared with market-implied probability
- How liquidity, edge threshold, and correlation reduce or reject a stake
- What is already implemented versus what would require a Kalshi-specific ingestion adapter

Ground the case study in existing code:

- `betting_system/markets/base.py`
- `betting_system/markets/kalshi.py`
- `betting_system/markets/polymarket.py`
- `betting_system/markets/market_scoring.py`
- `betting_system/markets/edge_evaluation.py`
- `betting_system/optimizer/portfolio.py`

Do not claim live trading or proprietary market performance unless the evidence exists.

## Phase 5: Deployment Evidence

Status: planned.

Create `docs/DEPLOYMENT_LOG.md` only after there is a real deployment URL or a documented local demo artifact.

Recommended content:

- Streamlit URL or local run instructions
- Data source status: live, fixture, or mixed
- Last refresh timestamp
- Known failure modes and mitigation
- Rollback path for model artifacts

Until then, keep Streamlit Cloud setup instructions in the README as deployment notes, not as a production claim.

## Verification Checklist

- [x] Production evidence checklist exists
- [x] README links evidence from the backtest section
- [x] Edge Desk writes durable market-edge logs
- [x] `/markets/edge-summary` exposes market-layer audit metrics
- [x] API and dashboard expose `data_source`
- [ ] `feat/edge-desk-terminal` is visible on `main`
- [ ] Prediction-market case study exists
- [ ] Deployment log exists after a real deployment is available
- [ ] `ruff check .` passes
- [ ] `pytest` passes

## Success Standard

The finished repo should let a recruiter or ML interviewer answer five questions without a live walkthrough:

1. What is the model predicting?
2. How do we know probabilities are calibrated?
3. How are stakes capped when forecasts are wrong or correlated?
4. Which results are synthetic, fixture-based, or live?
5. What would need to change to score Kalshi or Polymarket events in production?

That is the credibility bar. The model can be imperfect; the evidence trail cannot be fuzzy.
