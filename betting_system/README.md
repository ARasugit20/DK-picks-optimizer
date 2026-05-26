# ML Sports Betting Decision System

This is a **disciplined, test-first** ML system for DraftKings-style markets:

- Learn **calibrated hit probabilities** per leg (NBA props first)
- Compute **edge + EV** vs odds
- Build **small, risk-controlled** parlays
- Backtest with **walk-forward** evaluation

## Setup

From the repo root (`dk-ml-lab/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r betting_system/requirements.txt
export PYTHONPATH="$(pwd)"   # repo root — so `import betting_system` works
```

The dashboard bootstrap also adds the repo root to `sys.path`; keeping `PYTHONPATH` set matches pytest/uvicorn runs.

Set API keys (for odds ingestion):

```bash
export ODDS_API_KEY="..."
export STATS_API_KEY="..."
```

## Run tests

```bash
pytest -q betting_system/tests
```

## Run API

```bash
uvicorn betting_system.api.main:app --reload --host 127.0.0.1 --port 8000
```

## Run dashboard

From the repo root:

```bash
streamlit run betting_system/dashboard/app.py
```

If you see `ModuleNotFoundError: No module named 'betting_system'`, from the repo root run:

```bash
export PYTHONPATH="$(pwd)"
streamlit run betting_system/dashboard/app.py
```

## Next steps

- Add a stats ingestion module that produces `stat_results` parquet with `game_date`
- Train per `market_type` using `pipeline/train.py`
- Run `pipeline/backtest.py` over a real holdout period

