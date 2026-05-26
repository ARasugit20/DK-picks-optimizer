from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS_PATH = ROOT / "config" / "thresholds.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    odds_api_key: str = Field(default="", alias="ODDS_API_KEY")
    db_path: Path = Field(default=ROOT / "data" / "dk_picks.db", alias="DK_PICKS_DB_PATH")
    default_bankroll: float = Field(default=500.0, alias="DEFAULT_BANKROLL")
    artifacts_dir: Path = ROOT / "models" / "artifacts"


def load_thresholds() -> dict:
    if not THRESHOLDS_PATH.exists():
        return {}
    with THRESHOLDS_PATH.open() as f:
        return yaml.safe_load(f) or {}


settings = Settings()
