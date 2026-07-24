"""Write a lightweight model registry manifest for auditability."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from betting_system.config import validate_config


DEFAULT_OUT = Path("model_registry/artifact_manifest.json")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def build_model_manifest(
    *,
    config_path: str | Path = "betting_system/config.yaml",
    model_path: str | Path = "betting_system/data/processed/models/model.pkl",
    metrics_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build model artifact metadata without mutating the model."""
    cfg = validate_config(config_path)
    model = Path(model_path)
    metrics = Path(metrics_path) if metrics_path else None
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "config_path": str(config_path),
        "config_sha256": _sha256(Path(config_path)),
        "model_path": str(model),
        "model_exists": model.exists(),
        "model_sha256": _sha256(model),
        "metrics_path": str(metrics) if metrics else None,
        "metrics_sha256": _sha256(metrics) if metrics else None,
        "market_types": cfg.markets["types"],
        "calibration": cfg.training["calibration"],
        "risk_limits": {
            "kelly_fraction": cfg.model["kelly_fraction"],
            "max_stake_pct": cfg.model["max_stake_pct"],
            "max_parlay_pct": cfg.model["max_parlay_pct"],
            "max_slate_exposure": cfg.model["max_slate_exposure"],
            "correlation_max_pair": cfg.model["correlation_max_pair"],
        },
    }


def write_model_manifest(
    *,
    out_path: str | Path = DEFAULT_OUT,
    config_path: str | Path = "betting_system/config.yaml",
    model_path: str | Path = "betting_system/data/processed/models/model.pkl",
    metrics_path: str | Path | None = None,
) -> Path:
    """Write a model registry manifest and return its path."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_model_manifest(
        config_path=config_path,
        model_path=model_path,
        metrics_path=metrics_path,
    )
    out.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return out


def main() -> None:
    """CLI entrypoint for writing model manifest metadata."""
    parser = argparse.ArgumentParser(description="Write model artifact registry manifest")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--config", default="betting_system/config.yaml")
    parser.add_argument("--model", default="betting_system/data/processed/models/model.pkl")
    parser.add_argument("--metrics", default=None)
    args = parser.parse_args()
    print(
        write_model_manifest(
            out_path=args.out,
            config_path=args.config,
            model_path=args.model,
            metrics_path=args.metrics,
        )
    )


if __name__ == "__main__":
    main()
