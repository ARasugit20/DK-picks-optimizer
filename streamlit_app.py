"""Streamlit Community Cloud entrypoint (repo root)."""

from __future__ import annotations

import runpy
from pathlib import Path

_DASHBOARD = Path(__file__).resolve().parent / "betting_system" / "dashboard" / "app.py"
runpy.run_path(str(_DASHBOARD), run_name="__main__")
