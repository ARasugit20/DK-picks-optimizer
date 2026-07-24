# Fixture Smoke Evidence — 2026-07-23

This folder documents a reproducible fixture-mode validation run. It is not a live performance claim.

## Commands

```bash
pytest tests/pipeline/test_run_market_pipeline_smoke.py -v
pytest tests/test_artifact_schemas.py -v
python3 -m dk_picks.cli validate-config --path betting_system/config.yaml
```

## Expected Artifacts

Fixture market smoke writes temporary versions of:

- `market_opportunities.json`
- `prediction_markets.parquet`
- `market_edge_log.jsonl`

The files are generated in pytest temporary directories and are intentionally not committed as production evidence.

## Interpretation

Passing this run proves the repo can exercise the market pipeline without API keys or network access. It does not prove live alpha, model profitability, or venue execution quality.
