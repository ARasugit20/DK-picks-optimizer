from __future__ import annotations

import json
import sys
from pathlib import Path

# Streamlit executes this file directly; add repo root so `import betting_system` works.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from betting_system.config import load_settings


st.set_page_config(page_title="Betting System", layout="wide")

settings = load_settings()
processed = Path(settings.data["processed_data_path"])


st.title("ML Sports Betting Decision System")

page = st.sidebar.selectbox(
    "Page",
    ["Today's Picks", "Calibration", "Bankroll Tracker", "Backtester (logs)", "Model Health"],
)


def _load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


if page == "Today's Picks":
    data = _load_json(processed / "picks_today.json")
    if not data:
        st.info("No picks generated yet. Run pipeline to generate picks.")
    else:
        st.json(data)

elif page == "Calibration":
    data = _load_json(processed / "calibration_latest.json")
    if not data:
        st.info("No calibration data yet. Train a model first.")
    else:
        st.json(data)

elif page == "Bankroll Tracker":
    data = _load_json(processed / "bankroll.json")
    if not data:
        st.write({"bankroll": 1000.0, "exposure": 0.0, "pnl": 0.0})
    else:
        st.json(data)

elif page == "Backtester (logs)":
    log_path = processed / "backtest_log.jsonl"
    if not log_path.exists():
        st.info("No backtest logs yet. Run walk_forward_backtest.")
    else:
        rows = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            rows.append(json.loads(line))
        df = pd.DataFrame(rows)
        st.dataframe(df[["slate_id", "bankroll", "profit", "staked"]], use_container_width=True)
        st.line_chart(df.set_index("slate_id")["bankroll"])

else:
    st.write("Model health page (v1): metrics files live in `betting_system/models/leg_model/`.")
    st.write("Next: add feature importance, recent ROI, ECE trends.")

