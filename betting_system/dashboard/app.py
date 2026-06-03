from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from betting_system.config import load_settings
from betting_system.dashboard.demo_slate import demo_worthy_legs
from betting_system.dashboard.recommend import ParlayRecommendation, recommend_all_targets
st.set_page_config(
    page_title="DK Picks Optimizer",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

settings = load_settings()
dash_cfg = settings.dashboard
processed = Path(settings.data["processed_data_path"])


CARD_CSS = """
<style>
.pick-card {
  border: 1px solid #2d333b;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 10px;
  background: linear-gradient(90deg, #161b22 0%, #1c2128 100%);
}
.pick-card-hot { border-left: 4px solid #f97316; }
.pick-card-cold { border-left: 4px solid #38bdf8; }
.pick-name { font-size: 1.15rem; font-weight: 700; color: #f0f6fc; }
.pick-meta { color: #8b949e; font-size: 0.85rem; margin-top: 4px; }
.pick-line { font-size: 1.35rem; font-weight: 800; color: #3fb950; text-align: right; }
.pick-pct { font-size: 0.8rem; color: #8b949e; text-align: right; }
.rec-banner {
  background: #1f6feb22;
  border: 1px solid #1f6feb;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
}
</style>
"""


def _load_json(path: Path):
    """Load JSON from disk or return None."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_slate_legs() -> tuple[list[dict], str]:
    """Load legs from processed picks or demo pool."""
    data = _load_json(processed / "picks_today.json")
    use_demo = bool(dash_cfg.get("use_demo_when_empty", True))
    if data and data.get("worthy_legs"):
        return data["worthy_legs"], "live"
    if use_demo:
        return demo_worthy_legs(), "demo"
    return [], "empty"


def _heat_icon(p_hit: float) -> str:
    """Return fire/snowflake emoji by model confidence."""
    if p_hit >= 0.60:
        return "🔥"
    if p_hit < 0.56:
        return "❄️"
    return ""


def _render_leg_card(leg: dict, *, in_parlay: bool = False) -> None:
    """Render one player prop row (FantasyData-style)."""
    hot = "pick-card-hot" if float(leg.get("p_hit", 0)) >= 0.60 else ""
    cold = "pick-card-cold" if float(leg.get("p_hit", 0)) < 0.56 and not hot else ""
    cls = f"pick-card {hot or cold}".strip()
    score = leg.get("score_final") or leg.get("matchup", "")
    actual = leg.get("actual_stat")
    actual_txt = f" · Actual: <b>{actual:g}</b>" if actual is not None else ""
    border = "2px solid #3fb950" if in_parlay else "1px solid #2d333b"
    st.markdown(
        f"""
        <div class="{cls}" style="border:{border}">
          <table width="100%"><tr>
            <td width="8%"><span style="color:#8b949e">{leg.get('position','')}</span></td>
            <td width="52%">
              <div class="pick-name">{_heat_icon(float(leg.get('p_hit',0)))} {leg.get('player_name', leg.get('player_id'))}</div>
              <div class="pick-meta">{leg.get('side','')} {leg.get('line')} {leg.get('market_label','PTS')} · {score}{actual_txt}</div>
            </td>
            <td width="20%" class="pick-pct">Model {leg.get('model_confidence_pct', round(float(leg.get('p_hit',0))*100,1))}%</td>
            <td width="20%" class="pick-line">{leg.get('odds_american', '')}</td>
          </tr></table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_recommendation(rec: ParlayRecommendation) -> None:
    """Show one target-multiplier portfolio recommendation."""
    win_pct = rec.p_parlay * 100
    quality_note = (
        "Payout band matches your target."
        if rec.match_quality == "on_target"
        else "Closest available combo — true 10×/15× may need different leg count or odds."
    )
    st.markdown(
        f"""
        <div class="rec-banner">
          <b>{rec.leg_count}-leg portfolio → {rec.target_multiplier:.0f}× target</b><br/>
          Stake <b>${rec.stake:,.2f}</b> → payout if all hit <b>${rec.payout_if_win:,.2f}</b>
          ({rec.implied_multiplier:.2f}× implied) · Win prob <b>{win_pct:.2f}%</b> · EV/unit {rec.ev_per_unit:+.3f}<br/>
          <span style="color:#8b949e">{quality_note}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for leg in rec.legs:
        _render_leg_card(leg, in_parlay=True)


def _page_picks_builder() -> None:
    """Main picks page: bankroll, leg count, multiplier targets."""
    legs, source = _load_slate_legs()
    today = date.today().strftime("%a %b %d").upper()
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    st.title(f"NBA DraftKings Picks Tonight ({today})")
    if source == "demo":
        st.caption(
            "Demo slate — connect Odds API + run pipeline for live lines. "
            "Recommendations use calibrated probabilities from the optimizer."
        )
    elif source == "empty":
        st.warning("No slate data. Run the ingest/predict pipeline or enable demo mode in config.")
        return

    st.sidebar.header("Your play")
    bankroll = st.sidebar.number_input(
        "Amount to play ($)",
        min_value=5.0,
        max_value=100_000.0,
        value=float(dash_cfg.get("default_bankroll", 50.0)),
        step=5.0,
    )
    leg_count = st.sidebar.radio(
        "Legs in portfolio",
        options=list(dash_cfg.get("leg_count_options", [5, 10, 15])),
        index=0,
        horizontal=True,
    )
    mult_10 = st.sidebar.checkbox("Find best 10× play", value=True)
    mult_15 = st.sidebar.checkbox("Find best 15× play", value=True)
    run = st.sidebar.button("Get best picks", type="primary", use_container_width=True)

    worthy = sorted(legs, key=lambda x: float(x.get("p_hit", 0)), reverse=True)
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Props available", len(worthy))
    col_b.metric("Your stake", f"${bankroll:,.0f}")
    col_c.metric("Leg count", int(leg_count))

    if run:
        targets = []
        if mult_10:
            targets.append(10)
        if mult_15:
            targets.append(15)
        if not targets:
            st.error("Select at least one target: 10× or 15×.")
        else:
            recs = recommend_all_targets(
                worthy,
                bankroll=float(bankroll),
                leg_counts=[int(leg_count)],
                multipliers=targets,
            )
            if not recs:
                st.error("Could not build a portfolio — try fewer legs or a different stake.")
            else:
                st.success(
                    f"Top {len(recs)} pick(s) for ${bankroll:,.0f} on a {leg_count}-leg card "
                    f"(ranked by win probability vs payout target)."
                )
                for rec in recs:
                    st.divider()
                    _render_recommendation(rec)
    else:
        st.info("Set your amount and leg count, then click **Get best picks** for 10× / 15× recommendations.")

    st.subheader("All player props (sorted by model confidence)")
    for leg in worthy[:18]:
        _render_leg_card(leg)


def _page_other(name: str) -> None:
    """Secondary admin pages (calibration, logs)."""
    if name == "Calibration":
        data = _load_json(processed / "calibration_latest.json")
        st.json(data if data else {"message": "Train a model to populate calibration_latest.json"})
    elif name == "Capital Tracker":
        data = _load_json(processed / "bankroll.json")
        st.json(data if data else {"bankroll": 1000.0, "exposure": 0.0, "pnl": 0.0})
    elif name == "Walk-Forward Logs":
        log_path = processed / "backtest_log.jsonl"
        if not log_path.exists():
            st.info("No backtest logs yet.")
        else:
            rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            df = pd.DataFrame(rows)
            st.dataframe(df[["slate_id", "bankroll", "profit", "staked"]], use_container_width=True)
            st.line_chart(df.set_index("slate_id")["bankroll"])
    else:
        st.write("Model artifacts: `betting_system/models/leg_model/`")


page = st.sidebar.selectbox(
    "Page",
    ["Picks Tonight", "Calibration", "Capital Tracker", "Walk-Forward Logs", "Model Health"],
)

if page == "Picks Tonight":
    _page_picks_builder()
else:
    st.title(page)
    _page_other(page)
