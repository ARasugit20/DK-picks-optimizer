# Probabilistic Forecasting System (`betting_system/`)

Disciplined, test-first ML pipeline for sports prop markets:

- Learn **calibrated hit probabilities** per leg (NBA props first)
- Compute **model edge vs market-implied probability** and EV
- Build **small, risk-controlled correlated multi-leg portfolios**
- Backtest with **walk-forward** evaluation

## Setup

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$(pwd)"
```

Set API keys (for odds ingestion):

```bash
export ODDS_API_KEY="..."
export STATS_API_KEY="..."
```

## Run tests

```bash
pytest tests/ --cov=. --cov-fail-under=75
```

## Run API

```bash
uvicorn betting_system.api.main:app --reload --host 127.0.0.1 --port 8000
```

## Run dashboard

```bash
streamlit run streamlit_app.py
```

All thresholds (Kelly fraction, max stake %, ECE limits) live in `config.yaml`.
