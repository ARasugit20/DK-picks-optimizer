from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_logger(name: str = "betting_system") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    h = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    h.setFormatter(fmt)
    logger.addHandler(h)
    return logger


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")

