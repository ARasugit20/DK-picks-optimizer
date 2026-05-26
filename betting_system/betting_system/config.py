from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


@dataclass(frozen=True)
class Settings:
    raw: dict[str, Any]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def model(self) -> dict[str, Any]:
        return self.raw["model"]

    @property
    def training(self) -> dict[str, Any]:
        return self.raw["training"]

    @property
    def backtest(self) -> dict[str, Any]:
        return self.raw["backtest"]


def load_settings(config_path: str | Path = Path("betting_system/config.yaml")) -> Settings:
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found at {p.resolve()}")
    raw = yaml.safe_load(p.read_text())
    raw = _expand_env(raw)
    return Settings(raw=raw)

