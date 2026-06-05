# DK-Picks-Optimizer — Agent Execution Prompt

> Paste this entire file into Cursor as your project context when working on this repo.

## PROJECT GOAL

Harden this **probabilistic performance forecasting** system into an interview-proof ML portfolio flagship. **Do not rebuild existing ML.**

## WHAT EXISTS

- LightGBM + isotonic calibration, Kelly / portfolio optimizer, walk-forward backtest
- FastAPI, Streamlit Slate Optimizer (demo + live `picks_today.json`)
- `dk-pipeline --dry-run` end-to-end orchestrator
- CI (pytest + ruff, 80% cov), SHAP panel, `docs/INTERVIEW.md`
- Contextual features: `home_away`, `days_rest`, `back_to_back`

## OPTIONAL POLISH (not blocking)

1. Real walk-forward numbers in README backtest table
2. Live Odds API production ingest (needs keys + stats feed)
3. User-specific Streamlit Cloud badge URL

## RULES

- `pytest` after every change · `ruff check .`
- Config in `betting_system/config.yaml` — no magic numbers
- Google-style docstrings on public functions
- Professional language only (forecasting, capital allocation, portfolios)

## QUICK REFERENCE

| Command | Purpose |
|---------|---------|
| `dk-pipeline --dry-run` | Full fixture pipeline → `picks_today.json` |
| `pytest` | All tests (root + `betting_system/tests/`) |
| `streamlit run streamlit_app.py` | Dashboard |
| `python scripts/plot_calibration.py` | Regenerate calibration PNG |

See [`docs/DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) for full status.
