# Probability-to-Capital Engine

Edge Desk should be evaluated as more than a market scanner. The intended decision loop is:

```text
forecast fair probability
  -> compare against executable market price
  -> size exposure under uncertainty and correlation
  -> log the decision
  -> settle the contract
  -> audit money-weighted calibration and PnL
```

## Why Prediction-Market Startups Care

Prediction-market teams do not only need a model that says an event is 57% likely. They need a system that answers:

- Is the 57% forecast tradable after spread and slippage?
- How much capital should respond?
- What correlated exposure already exists?
- Did large positions resolve at the forecasted rate?
- Was positive PnL caused by model edge, sizing, or execution quality?

## New Engine Pieces

| Layer | Code | Purpose |
|-------|------|---------|
| Executable price | `betting_system/markets/order_book.py` | Estimates average fill price, slippage, partial fill, and executable edge |
| Trade ledger | `betting_system/markets/ledger.py` | Stores market, side, quantity, fair value, entry price, settlement, and PnL |
| Money-weighted metrics | `betting_system/markets/money_weighted.py` | Reports ROI, notional-weighted Brier, and notional-weighted edge |
| API attribution | `/markets/pnl-attribution` | Exposes trade count and money-weighted capital outcomes |

## Interpretation

Plain calibration asks whether 60% forecasts resolve 60% of the time. Money-weighted calibration asks whether the capital behind those forecasts resolved correctly:

```text
small 60% forecast loses: low impact
large 60% forecast loses: high impact
```

That distinction matters because investors experience returns in dollars, not rows.

## Remaining Work

- Ingest real order-book depth from Kalshi/Polymarket instead of synthetic levels.
- Attach each paper/live order to a forecast artifact version.
- Add correlation-driver exposure by category, venue, and event family.
- Archive settled live ledgers under `docs/evidence/` before making performance claims.
