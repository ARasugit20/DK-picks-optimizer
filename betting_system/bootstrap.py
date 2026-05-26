"""Ensure repo root is on sys.path for direct script execution (Streamlit, etc.)."""

from __future__ import annotations

import sys
from pathlib import Path


def setup_path() -> Path:
    # betting_system/bootstrap.py -> parents[1] is repo root (dk-ml-lab/)
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root
