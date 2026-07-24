# Security and Compliance Notes

## Scope

This project is a forecasting and capital-allocation demo. It does not place real-money trades, hold customer funds, or provide financial advice.

## Secrets

- API keys must be provided through environment variables.
- `.env` is ignored.
- `betting_system/config.yaml` may reference `${ODDS_API_KEY}` and `${STATS_API_KEY}` but must not contain real secrets.

## Data Provenance

Every market-facing artifact should preserve whether data came from:

- `live`
- `fixture_fallback`

Fixture data is valid for CI and demos. It is not valid evidence of live profitability.

## Auditability

Decision and outcome evidence is split into durable logs:

- `market_edge_log.jsonl` records fair-value probability at scoring time.
- `market_edge_resolutions.jsonl` records settled outcomes.
- `market_trade_ledger.jsonl` records paper/live trades, fills, and PnL.

## Responsible Use

- Recommendations are decision support, not instructions to trade.
- Live deployment should add venue-specific compliance checks before order placement.
- Any real-money workflow needs authentication, authorization, custody controls, audit logging, and review of applicable law and venue rules.

## Failure Modes

- API outage: use fixture fallback and mark `data_source` clearly.
- Bad config: fail fast with `dk-picks validate-config`.
- Missing model artifact: `/model/status` reports unavailable.
- Missing settlement data: `/markets/pnl-attribution` reports pending/empty metrics.

## Big-Tech Review Notes

The system demonstrates the controls expected in regulated or risk-sensitive environments:

- explicit provenance
- validated configuration
- testable offline mode
- artifact contracts
- audit logs
- read-only API evidence endpoints
