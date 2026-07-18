# Test & Validation Runbook

Use this checklist before pushing changes that affect pipeline behavior, optimizer logic, or config loading.

## Offline Market Smoke

```bash
pytest tests/pipeline/test_run_market_pipeline_smoke.py -v
```

Verifies that fixture mode writes:

- `market_opportunities.json`
- `prediction_markets.parquet`
- durable Edge Desk edge logs

The smoke test monkeypatches live market clients to fail if any network path is touched.

## Optimizer Guards

```bash
pytest tests/optimizer/ -v
```

Verifies that portfolio construction respects:

- `correlation_max_pair`
- `max_parlays_per_slate`
- `max_stake_pct`
- `max_slate_exposure`

## Config Validation

```bash
python3 -m dk_picks.cli validate-config --path betting_system/config.yaml
pytest tests/test_config_validation.py -v
```

Expected success output:

```text
config OK
```

Validation catches out-of-range Kelly/exposure caps, missing required keys, and missing config files before pipeline execution.

## Full Gate

```bash
pytest --cov=. --cov-fail-under=80
ruff check .
```

The CI target is at least 80% coverage.

## Probability-to-Capital Layer

```bash
pytest tests/test_order_book.py tests/test_market_ledger.py tests/test_money_weighted.py tests/test_api.py -v
```

Verifies executable edge, ledger settlement, money-weighted calibration, and `/markets/pnl-attribution`.
