# Interview Card — 60-Second Answers

## What is walk-forward backtesting and why does it matter?

Walk-forward backtesting trains only on past slates and evaluates on the next unseen period, then rolls the window forward. It mimics production: you never use future outcomes to fit today's model. That matters because random or in-sample splits inflate ROI and calibration metrics. Here, each week’s capital allocation uses models fit strictly before that week, so reported hit rate, Brier, and Kelly stakes reflect what you could actually have deployed.

## What is isotonic calibration and why did you use it instead of Platt scaling?

Isotonic regression learns a monotonic mapping from raw scores to calibrated probabilities without assuming a logistic shape. Platt scaling (sigmoid) works well when miscalibration is roughly logit-linear. Prop models often distort tails; isotonic fixes bin-wise frequency error while preserving ranking. We fall back to sigmoid only if expected calibration error exceeds the threshold in `config.yaml`, keeping probabilities honest for Kelly sizing.

## What is Kelly criterion and what are its limitations?

Kelly sizes stakes to maximize long-run log-growth given edge and odds. We use fractional Kelly (`kelly_fraction` in config) because full Kelly is volatile and sensitive to probability error. Limitations: it assumes known probabilities, independent bets (we partially handle correlation via portfolio filters), and unlimited bankroll. Real slates need hard caps — `max_stake_pct`, `max_parlay_pct`, and `max_slate_exposure` — which this system enforces from config, not hard-coded constants.

## How did you prevent data leakage in your feature pipeline?

All rolling and EWM stats use `shift(1)` within player/stat groups before aggregating, so game *t* features only see games `< t`. Train/validation splits are strictly by `game_date`. Opening odds features use the earliest ingest per line, never closing lines from the same game. Tests assert the first row has no rolling mean and later rows match hand-computed past-only values.

## What does Brier score measure and what's a "good" score?

Brier score is mean squared error between predicted probability and the binary outcome (0/1). Lower is better; 0.25 is uninformative for a 50/50 base rate. For prop legs in the 0.45–0.65 range, we target Brier **below 0.25** on walk-forward holdout as "well-calibrated enough to size capital." It penalizes both sharpness and calibration, unlike accuracy alone.

## How would you scale this to real-time with 100k users?

Separate the path: async ingest workers write Parquet/S3; feature store serves precomputed rolling stats; model inference runs in a stateless FastAPI pool with cached artifacts; the portfolio optimizer is CPU-cheap and horizontally scaled. Use Redis for slate snapshots, CDN for dashboard reads, and queue-based retraining — not synchronous train on request. Postgres or Dynamo for audit logs; rate-limit `/picks/today` per API key. Walk-forward metrics stay offline in batch; online serving only loads the latest blessed model version.

## How do you prove the results are real and not demo numbers?

The README labels synthetic rows as demonstration data. Production claims should come from the evidence trail in `docs/PRODUCTION_EVIDENCE.md`: archived walk-forward JSONL logs, regenerated calibration plots, live-feed metadata showing whether APIs or fixtures were used, and measured API readiness metrics. I would rather show a modest real holdout than an impressive synthetic table, because the interview value is leakage control, calibration discipline, and reproducible allocation decisions.

## How do you know Edge Desk's edge is real and not fixture noise?

I log every market opportunity at scoring time with its market price, fair-value probability, edge, data source, and timestamp. Once a contract settles, I append the realized YES/NO outcome and evaluate that market-layer log separately from the sports-prop model. The `/markets/edge-summary` endpoint reports resolved count, Brier, ECE, mean realized edge, and an approximate one-sample test of realized edge versus zero. Fixture rows prove the audit wiring; live claims require settled live contracts in `market_edge_resolutions.jsonl`.
