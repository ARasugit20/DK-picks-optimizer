# Changelog

All notable changes to DK-Picks-Optimizer are documented here.

## [Unreleased]

### Added
- Pydantic response models for all FastAPI routes with artifact validation at the API boundary.
- Structured request logging middleware (`request_id`, route, latency, artifact version).
- Calibration proof tests asserting holdout ECE improvement per market type.
- Hypothesis property tests for parlay correlation discount invariants.
- End-to-end temporal leakage test for `build_features()` artifacts.
- Expanded config validation for calibration methods and ECE cross-checks.
- Training artifact provenance metadata (`artifact_version`, `git_sha`, `config_fingerprint`, `dataset_window`).

### Changed
- `train_market_type()` persists calibrated and uncalibrated holdout ECE for auditability.
- Coverage configuration now includes API and training modules in measured paths.
- `correlation_discount_default` config knob is applied for unknown pairwise correlations.

## [0.1.0] - 2026-06-01

### Added
- Initial calibrated prop forecasting pipeline and Edge Desk prediction-market terminal.
- Portfolio optimizer with Kelly staking and correlation-aware parlay construction.
- Streamlit dashboard, FastAPI backend, and fixture-backed market pipeline.
