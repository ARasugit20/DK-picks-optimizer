from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


class FlexibleModel(BaseModel):
    """Base config section model that validates known keys and allows growth."""

    model_config = ConfigDict(extra="allow")

    def __getitem__(self, key: str) -> Any:
        """Support legacy section["key"] access."""
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        """Support legacy section.get("key") access."""
        return getattr(self, key, default)


class MarketConfig(FlexibleModel):
    primary: str
    types: list[str]


class ModelConfig(FlexibleModel):
    random_seed: int
    kelly_fraction: float = Field(gt=0.0, le=1.0)
    min_edge: float = Field(ge=0.0, le=1.0)
    max_legs_per_parlay: int = Field(ge=1)
    max_parlays_per_slate: int = Field(ge=1)
    max_stake_pct: float = Field(gt=0.0, le=1.0)
    max_parlay_pct: float = Field(gt=0.0, le=1.0)
    max_slate_exposure: float = Field(gt=0.0, le=1.0)
    min_p_hit: float = Field(ge=0.0, le=1.0)
    min_leg_odds_american: int
    max_leg_odds_american: int
    correlation_max_pair: float = Field(ge=0.0, le=1.0)
    correlation_default_pair: float = Field(ge=-1.0, le=1.0)
    correlation_discount_default: float = Field(ge=0.0, le=1.0)
    worthy_requires_positive_ev: bool

    @model_validator(mode="after")
    def _validate_exposure_caps(self) -> ModelConfig:
        if self.max_parlay_pct > self.max_slate_exposure:
            raise ValueError("max_parlay_pct must be <= max_slate_exposure")
        if self.min_leg_odds_american > self.max_leg_odds_american:
            raise ValueError("min_leg_odds_american must be <= max_leg_odds_american")
        return self


class FeatureConfig(FlexibleModel):
    season_games: int = Field(gt=0)
    rolling_windows: list[int]
    ewm_span: int = Field(gt=0)

    @field_validator("rolling_windows")
    @classmethod
    def _rolling_windows_positive(cls, value: list[int]) -> list[int]:
        if not value or any(window <= 0 for window in value):
            raise ValueError("rolling_windows must contain positive integers")
        return value


class CalibrationConfig(FlexibleModel):
    ece_threshold: float = Field(ge=0.0, le=1.0)
    ece_test_max: float = Field(ge=0.0, le=1.0)
    primary_method: str
    fallback_method: str
    calibration_plot_bins: int = Field(gt=0)


class TrainingConfig(FlexibleModel):
    optuna_trials: int = Field(ge=0)
    lgbm_n_estimators: int = Field(gt=0)
    lgbm_learning_rate: float = Field(gt=0.0)
    retrain_frequency_days: int = Field(gt=0)
    calibration: CalibrationConfig


class BacktestConfig(FlexibleModel):
    walk_forward_weeks: int = Field(gt=0)
    min_sample_parlays: int = Field(ge=0)
    baseline_compare: bool


class DataConfig(FlexibleModel):
    odds_api_key: str
    stats_api_key: str
    raw_data_path: str
    processed_data_path: str
    odds_history_path: str
    models_path: str
    db_url: str


class ApiConfig(FlexibleModel):
    host: str
    port: int = Field(gt=0, le=65535)


class DashboardConfig(FlexibleModel):
    port: int = Field(gt=0, le=65535)
    default_bankroll: float = Field(gt=0.0)
    leg_count_options: list[int]
    multiplier_targets: list[int]
    multiplier_tolerance_pct: float = Field(ge=0.0, le=1.0)
    max_pool_legs: int = Field(gt=0)
    use_demo_when_empty: bool
    default_objective_mode: str


class OddsConfig(FlexibleModel):
    bookmakers: str
    regions: str


class StatsConfig(FlexibleModel):
    season: str
    cache_enabled: bool


class MappingConfig(FlexibleModel):
    fuzzy_threshold: float = Field(ge=0.0, le=1.0)
    min_join_rate: float = Field(ge=0.0, le=1.0)


class RecommendationsConfig(FlexibleModel):
    prob_weight: float = Field(ge=0.0)
    ev_weight: float = Field(ge=0.0)
    correlation_penalty_weight: float = Field(ge=0.0)
    target_multiplier_weight: float = Field(ge=0.0)


class SequenceConfig(FlexibleModel):
    enabled: bool
    seq_len: int = Field(gt=0)
    embedding_dim: int = Field(gt=0)
    epochs: int = Field(gt=0)


class PredictionMarketsConfig(FlexibleModel):
    enabled: bool
    sources: dict[str, Any]
    categories: list[str]
    curation: dict[str, Any]
    scoring: dict[str, Any]
    ui: dict[str, Any]
    fixture_fallback: bool


class BettingSystemConfig(BaseSettings):
    """Validated betting-system YAML configuration."""

    model_config = SettingsConfigDict(extra="allow")

    markets: MarketConfig
    model: ModelConfig
    features: FeatureConfig
    training: TrainingConfig
    backtest: BacktestConfig
    data: DataConfig
    api: ApiConfig
    dashboard: DashboardConfig
    odds: OddsConfig
    stats: StatsConfig
    mapping: MappingConfig
    recommendations: RecommendationsConfig
    sequence: SequenceConfig
    prediction_markets: PredictionMarketsConfig

    @property
    def raw(self) -> dict[str, Any]:
        """Return a dict matching the legacy Settings.raw shape."""
        return self.model_dump(mode="python")


Settings = BettingSystemConfig


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load and validate betting_system/config.yaml."""
    if config_path is None:
        config_path = os.environ.get("BETTING_CONFIG_PATH", "betting_system/config.yaml")
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found at {p.resolve()}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    raw = _expand_env(raw)
    return BettingSystemConfig.model_validate(raw)


def validate_config(config_path: str | Path | None = None) -> BettingSystemConfig:
    """Validate a config file and return the parsed config."""
    return load_settings(config_path)
