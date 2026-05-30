# DK-Picks-Optimizer — Production Hardening Cursor Prompt

> Paste this entire file into Cursor as your project context when working on this repo.

## PROJECT GOAL

Transform this ML sports betting optimizer from a working prototype into a production-grade, interview-proof portfolio flagship. Every change must be testable, explainable, and demonstrable in a live interview.

## WHAT EXISTS (do not rebuild, only improve)

- LightGBM leg model with isotonic calibration
- Kelly criterion + portfolio optimizer
- Walk-forward backtester
- FastAPI endpoints
- Streamlit dashboard

## TASK LIST — implement in this exact order

### TASK 1: CI/CD Pipeline (GitHub Actions)

Create `.github/workflows/ci.yml` that:

- Runs on every push to main and every PR
- Installs dependencies via pip (`requirements.txt`)
- Runs: `pytest tests/ --cov=. --cov-report=term-missing --cov-fail-under=75`
- Runs: `ruff check .` (linting)
- Adds a CI badge to README.md: `[![CI](repo_url/actions/badge.svg)]`
- MUST pass before anything else is considered done

### TASK 2: Backtest Results Section in README

Add a section called `## Backtest Results` to README.md containing:

- A markdown table with columns: Week, ROI (%), Hit Rate (%), Brier Score, Kelly Stake
- Minimum 8 rows of walk-forward results (use real or synthetic data — label clearly)
- A calibration interpretation: "Model is well-calibrated when Brier < 0.25"
- A baseline comparison row: "Random selection", "Chalk-only (lowest odds)"
- One sentence per metric explaining what it means in plain English

### TASK 3: Architecture Diagram in README

Add a mermaid diagram showing:

```
Data Sources (Odds API, Stats API)
  → ingest.py (raw JSON → Parquet)
  → features.py (rolling features, leakage-free)
  → train.py (LightGBM + isotonic calibration)
  → predict.py (p_hit, edge per leg)
  → optimizer/ (parlay builder → Kelly staking → portfolio)
  → FastAPI /picks/today
  → Streamlit dashboard
```

### TASK 4: Calibration Plot (saved as PNG)

In a script called `scripts/plot_calibration.py`:

- Load model predictions and actual outcomes from backtest results
- Use `sklearn.calibration.calibration_curve` to generate reliability diagram
- Plot with matplotlib: predicted probability vs actual frequency, 10 bins
- Add a perfectly-calibrated reference line (y=x)
- Save to `docs/calibration_plot.png`
- Embed in README.md under Backtest Results section

### TASK 5: Streamlit Deploy

- Ensure `dashboard/app.py` runs fully with: `streamlit run dashboard/app.py`
- Add a `requirements.txt` that includes every import used
- Deploy to Streamlit Community Cloud (streamlit.io/cloud) — FREE
- Add the live URL to README.md header as a badge: `[Live Demo →]`

### TASK 6: Repo Description + Framing (non-gambling language)

Change ALL language that sounds like gambling to professional ML language:

- "picks" → "prop predictions" or "leg forecasts"
- "betting system" → "probabilistic forecasting system"
- "parlays" → "correlated multi-leg portfolios"
- "bankroll" → "capital allocation"
- "edge" → "model edge vs market-implied probability"

GitHub repo description: "End-to-end ML pipeline for calibrated probability forecasting and constrained portfolio optimization · LightGBM · isotonic calibration · walk-forward backtest · FastAPI · Streamlit"

### TASK 7: Tests

Create `tests/` folder with at minimum:

- `test_features.py`: assert no data leakage (future data not used in rolling features)
- `test_calibration.py`: assert ECE (Expected Calibration Error) < 0.10 on test set
- `test_optimizer.py`: assert Kelly stake never exceeds MAX_STAKE_PCT config
- `test_api.py`: assert GET /picks/today returns 200 with correct schema

Run: `pytest tests/ -v` and confirm all pass

### TASK 8: Interview Card (`docs/INTERVIEW.md`)

Create a file with exactly these Q&As you can say out loud in 60 seconds each:

- Q: What is walk-forward backtesting and why does it matter?
- Q: What is isotonic calibration and why did you use it instead of Platt scaling?
- Q: What is Kelly criterion and what are its limitations?
- Q: How did you prevent data leakage in your feature pipeline?
- Q: What does Brier score measure and what's a "good" score?
- Q: How would you scale this to real-time with 100k users?

## RULES

- Run pytest after EVERY task. Do not move to next task if tests fail.
- No magic numbers — everything configurable in `config.yaml`
- Every function must have a docstring
- README must be updated as you go, not at the end
- Do NOT add new ML models — improve what exists
