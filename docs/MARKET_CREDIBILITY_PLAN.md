# Market Credibility Improvement Plan

## Objective

Position DK-Picks-Optimizer as a recruiter-ready forecasting and allocation system for prediction-market work. The project should stay honest about what is proven today, while making it easy for a Kalshi, Polymarket, or quant hiring team to verify calibration, leakage control, risk sizing, and live-feed readiness.

## Current Gap

The codebase already has the core technical pieces:

- LightGBM with isotonic calibration
- Walk-forward backtest machinery
- Fixture and live-style market pipelines
- FastAPI and Streamlit surfaces
- Kelly sizing with exposure and correlation constraints
- Tests for leakage, calibration, API schemas, markets, and optimizer behavior

The remaining gap is evidence, not model architecture. Recruiters should not have to infer whether the README numbers are demo data, where the logs live, or how sports-prop logic maps to binary event markets.

## Phase 1: Merge and Reposition

Status: in progress.

Actions:

- Merge `feat/edge-desk-terminal` into `main` so the default GitHub page shows the current Edge Desk positioning.
- Keep sports props as the proof domain, but describe the system as a market-agnostic probability and allocation engine.
- Keep the README backtest section explicit that the displayed table is synthetic until replaced by archived walk-forward logs.
- Link [PRODUCTION_EVIDENCE.md](PRODUCTION_EVIDENCE.md) wherever performance claims appear.

Why it matters: a stale default branch makes the project look unfinished even when the feature branch has the stronger story.

## Phase 2: Proof Trail

Status: partially complete.

Artifacts already present:

- [PRODUCTION_EVIDENCE.md](PRODUCTION_EVIDENCE.md)
- [calibration_plot.png](calibration_plot.png)
- `betting_system/pipeline/backtest.py`
- `betting_system/pipeline/run_market_pipeline.py`
- `betting_system/data/processed/picks_today.json` when generated locally
- `betting_system/data/processed/market_opportunities.json` when generated locally

Next actions:

- Add a committed sample summary generated from a real or clearly labeled fixture run.
- Keep generated model/data artifacts out of Git unless they are intentionally small, documented evidence files.
- Add an evidence section to the README only after the source artifact is archived.

Runbook:

```bash
export PYTHONPATH="$(pwd)"
dk-pipeline --dry-run
python -m betting_system.pipeline.run_market_pipeline --fixture
python scripts/plot_calibration.py
```

Production runs require live API credentials and should preserve metadata showing whether each output came from live data or fixture fallback.

## Phase 3: Prediction-Market Case Study

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
- `betting_system/optimizer/portfolio.py`

Do not claim live trading or proprietary market performance unless the evidence exists.

## Phase 4: Interview and Technical Depth

Status: planned.

Expand [INTERVIEW.md](INTERVIEW.md) with prediction-market questions:

- How would this handle a Kalshi binary event?
- What happens when model probability equals market price?
- How do you know calibration will hold on a new market?

Create `docs/TECHNICAL_DEPTH.md` for senior ML review:

- Model and calibration choices
- Time-series split and leakage controls
- Risk and exposure limits from `betting_system/config.yaml`
- Failure modes: calibration drift, API fallback, missing model artifacts, thin liquidity
- Tests that verify the claims

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
- [x] README links evidence from the backtest section on `feat/edge-desk-terminal`
- [ ] `feat/edge-desk-terminal` is visible on `main`
- [ ] Prediction-market case study exists
- [ ] Interview guide includes market-specific Q&A
- [ ] Technical depth document exists
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
