import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dk_picks.backtest.metrics import calibration_report, pick_performance
from dk_picks.config import settings
from dk_picks.recommend import generate_recommendations

st.set_page_config(page_title="DK Picks Optimizer", layout="wide")
st.title("DK Picks Optimizer")
st.caption("Calibrated ML + bankroll sizing + correlation-aware parlays")

bankroll = st.sidebar.number_input("Bankroll ($)", min_value=50.0, value=float(settings.default_bankroll))
max_parlays = st.sidebar.slider("Max parlays", 1, 20, 10)

if st.sidebar.button("Generate recommendations"):
    with st.spinner("Running models..."):
        rec = generate_recommendations(bankroll=bankroll, max_parlays=max_parlays)
    st.session_state["rec"] = rec

rec = st.session_state.get("rec")
if rec:
    singles = rec["singles"]
    st.subheader("Singles")
    if singles is not None and not singles.empty:
        st.dataframe(
            singles[
                ["sport", "home_team", "away_team", "market", "outcome", "model_prob", "edge", "ev", "stake"]
            ].head(25),
            use_container_width=True,
        )
    else:
        st.info("No singles met edge/confidence thresholds.")

    st.subheader("Parlays")
    if rec["parlays"]:
        st.dataframe(pd.DataFrame(rec["parlays"]), use_container_width=True)
    else:
        st.info("No parlays met thresholds.")

st.divider()
st.subheader("Historical performance")
perf = pick_performance()
if perf.empty:
    st.write("Log picks via CLI (`dk-picks recommend --save`) and import results CSV.")
else:
    st.metric("Hit rate", f"{perf['won'].mean():.1%}")
    st.metric("ROI (unit stakes)", f"{perf['pnl'].sum() / perf['stake'].sum():.2%}")
    st.json(calibration_report())
