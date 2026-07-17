"""Prediction-market trading terminal page for Streamlit."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from betting_system.config import load_settings
from betting_system.dashboard.market_data import get_market_by_id, load_market_opportunities
from betting_system.dashboard.terminal_styles import TERMINAL_CSS, edge_bar_html, fmt_pct, fmt_usd
from betting_system.pipeline.run_market_pipeline import run_market_pipeline


def _render_top_strip(data: dict[str, Any]) -> None:
    """Sticky account and source freshness strip."""
    meta = data.get("meta", {})
    acct = data.get("account", {})
    is_live = meta.get("is_live", False)
    badge = '<span class="badge-live">LIVE</span>' if is_live else '<span class="badge-fixture">FIXTURE</span>'
    sources = ", ".join(meta.get("sources", [])) or "none"
    fetched = meta.get("fetched_at", "unknown")[:19].replace("T", " ")
    fallback = meta.get("fallback_reason") or ""
    st.markdown(
        f"""
        <div class="top-strip">
          <span class="brand">EDGE DESK</span>
          {badge}
          <span style="color:#8b949e;font-size:0.75rem">Proprietary accuracy model</span>
          <div style="flex:1"></div>
          <div class="stat-block"><span class="stat-label">Account equity</span>
            <span class="stat-value accent">${acct.get('equity', 0):,.2f}</span></div>
          <div class="stat-block"><span class="stat-label">Edge captured today</span>
            <span class="stat-value positive">+${acct.get('daily_edge_captured', 0):,.2f}</span></div>
          <div class="stat-block"><span class="stat-label">Open P&L</span>
            <span class="stat-value positive">+${acct.get('open_pnl', 0):,.1f}</span></div>
          <div class="stat-block"><span class="stat-label">Source</span>
            <span class="stat-value" style="font-size:0.8rem">{sources} · {fetched}</span></div>
        </div>
        {"<div style='color:#8b949e;font-size:0.72rem;padding:4px 18px;background:#010409'>" + fallback + "</div>" if fallback else ""}
        """,
        unsafe_allow_html=True,
    )


def _render_hero(hero: dict[str, Any]) -> None:
    """Hero pick of the day card."""
    edge = hero.get("edge_pct", hero.get("edge", 0) * 100)
    st.markdown(
        f"""
        <div class="hero-card">
          <div style="display:flex;justify-content:space-between;align-items:start">
            <div>
              <div style="color:#3fb950;font-size:0.7rem;font-weight:600;letter-spacing:0.08em">PICK OF THE DAY</div>
              <div class="hero-title">{hero.get('question', '')}</div>
              <div class="hero-meta">
                <span class="tag venue">{hero.get('venue','').upper()}</span>
                <span class="tag">{hero.get('category','')}</span>
                Vol {fmt_usd(float(hero.get('volume') or 0))}
              </div>
            </div>
            <div style="text-align:right">
              <div class="hero-metric-label">Payout</div>
              <div class="hero-metric-val" style="color:#58a6ff">{hero.get('payout_multiplier', 0):.2f}x</div>
            </div>
          </div>
          <div class="hero-grid">
            <div class="hero-metric"><div class="hero-metric-label">Model confidence</div>
              <div class="hero-metric-val" style="color:#3fb950">{hero.get('confidence_pct', fmt_pct(hero.get('model_prob', 0), 0))}</div></div>
            <div class="hero-metric"><div class="hero-metric-label">Market price</div>
              <div class="hero-metric-val">{fmt_pct(hero.get('market_price', 0), 0)}</div></div>
            <div class="hero-metric"><div class="hero-metric-label">Model fair</div>
              <div class="hero-metric-val">{fmt_pct(hero.get('fair_price', hero.get('model_prob', 0)), 0)}</div></div>
            <div class="hero-metric"><div class="hero-metric-label">Edge vs market</div>
              <div class="hero-metric-val" style="color:#3fb950">+{edge:.1f}%</div></div>
          </div>
          {edge_bar_html(edge)}
          <div class="rationale">{hero.get('rationale', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("BUY YES", key="hero_yes", use_container_width=True, type="primary"):
            st.session_state["order_market_id"] = hero.get("market_id")
            st.session_state["order_side"] = "YES"
    with c2:
        if st.button("BUY NO", key="hero_no", use_container_width=True):
            st.session_state["order_market_id"] = hero.get("market_id")
            st.session_state["order_side"] = "NO"


def _render_feed_card(m: dict[str, Any], rank: int, selected: bool) -> None:
    """One ranked opportunity row."""
    edge = m.get("edge_pct", m.get("edge", 0) * 100)
    sel = "selected" if selected else ""
    st.markdown(
        f"""
        <div class="feed-card {sel}">
          <div style="display:flex;gap:10px;align-items:flex-start">
            <span class="feed-rank">{rank}</span>
            <div style="flex:1">
              <div class="feed-q">{m.get('question','')}</div>
              <div class="feed-tags">
                <span class="tag venue">{m.get('venue','').upper()}</span>
                <span class="tag">{m.get('category','')}</span>
                <span class="tag edge">+{edge:.1f}% edge</span>
                <span class="tag">Conf {m.get('confidence_pct', fmt_pct(m.get('model_prob',0),0))}</span>
                <span class="tag">Mkt {fmt_pct(m.get('market_price',0),0)}</span>
                <span class="tag">{fmt_usd(float(m.get('volume') or 0))}</span>
              </div>
              {edge_bar_html(edge, 60)}
            </div>
            <div style="text-align:right;min-width:50px">
              <div style="font-family:'IBM Plex Mono',monospace;font-weight:700;color:#58a6ff">
                {m.get('payout_multiplier', 0):.1f}x</div>
              <div style="color:#484f58;font-size:0.65rem">payout</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_detail_chart(market: dict[str, Any]) -> None:
    """Probability-over-time chart for selected market."""
    hist_m = market.get("price_history_market") or []
    hist_model = market.get("price_history_model") or []
    if not hist_m:
        st.info("No price history available.")
        return
    days = [f"D-{len(hist_m)-i-1}" if i < len(hist_m) - 1 else "Now" for i in range(len(hist_m))]
    df = pd.DataFrame({"Day": days, "Market": [p * 100 for p in hist_m], "Model fair": [p * 100 for p in hist_model]})
    st.markdown("#### Probability — model vs market")
    st.caption("Source: Edge Desk model · last 7 observations · probabilities in %")
    st.line_chart(df.set_index("Day"), color=["#58a6ff", "#3fb950"])
    edge = market.get("edge_pct", market.get("edge", 0) * 100)
    st.markdown(
        f"<div class='rationale'>Divergence: model leads market by <b>+{edge:.1f} pts</b>. "
        f"{market.get('rationale', '')}</div>",
        unsafe_allow_html=True,
    )


def _render_portfolio(portfolio: list[dict[str, Any]]) -> None:
    """Open positions strip."""
    st.markdown('<div class="panel-box"><div class="panel-title">Open Positions</div>', unsafe_allow_html=True)
    for p in portfolio:
        st.markdown(
            f"""
            <div class="pos-row">
              <div><div style="font-weight:600">{p.get('question','')[:42]}</div>
                <div style="color:#8b949e;font-size:0.72rem">{p.get('side')} · {p.get('qty')} @ {fmt_pct(p.get('avg_price',0),0)}</div></div>
              <div style="text-align:right"><div class="pos-pnl">+${p.get('pnl',0):.1f}</div>
                <div style="color:#8b949e;font-size:0.72rem">mkt {fmt_pct(p.get('mark_price',0),0)}</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_order_ticket(market: dict[str, Any] | None, side: str, contracts: int) -> None:
    """Bet slip / order ticket."""
    st.markdown('<div class="panel-box"><div class="panel-title">Order Ticket</div>', unsafe_allow_html=True)
    if not market:
        st.markdown("<div style='color:#8b949e;font-size:0.82rem'>Select a market to build an order.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    price = market.get("market_price", 0.5) if side == "YES" else 1 - market.get("market_price", 0.5)
    cost = contracts * price
    max_payout = contracts * 1.0
    mult = 1 / price if 0 < price < 1 else 0
    edge = market.get("edge_pct", market.get("edge", 0) * 100)
    st.markdown(
        f"""
        <div style="font-weight:600;font-size:0.88rem;margin-bottom:8px">{market.get('question','')}</div>
        <div class="pos-row"><span style="color:#8b949e">Side</span><span>{side}</span></div>
        <div class="pos-row"><span style="color:#8b949e">Limit price</span><span>{fmt_pct(price,1)}</span></div>
        <div class="pos-row"><span style="color:#8b949e">Model edge</span><span style="color:#3fb950">+{edge:.1f}%</span></div>
        <div class="pos-row"><span style="color:#8b949e">Contracts</span><span>{contracts}</span></div>
        <div class="pos-row"><span style="color:#8b949e">Est. cost</span><span>${cost:.2f}</span></div>
        <div class="pos-row"><span style="color:#8b949e">Max payout</span>
          <span style="color:#58a6ff">${max_payout:.2f} ({mult:.2f}x)</span></div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Submit order", key="submit_order", use_container_width=True, type="primary"):
        st.success(f"Paper order: {side} x{contracts} @ {fmt_pct(price,1)}")
    st.markdown("</div>", unsafe_allow_html=True)


def page_prediction_terminal() -> None:
    """Main prediction-market terminal page."""
    st.markdown(TERMINAL_CSS, unsafe_allow_html=True)
    pm_cfg = load_settings().raw.get("prediction_markets", {})

    with st.sidebar:
        st.header("Edge Desk")
        if st.button("Refresh live markets", use_container_width=True):
            with st.spinner("Fetching markets..."):
                try:
                    run_market_pipeline(use_fixture=False)
                except Exception:
                    run_market_pipeline(use_fixture=True)
                st.rerun()
        if st.button("Load fixtures", use_container_width=True):
            run_market_pipeline(use_fixture=True)
            st.rerun()

        categories = ["All"] + list(pm_cfg.get("categories", []))
        category = st.radio("Category", categories, index=0)
        sort_by = st.radio("Sort by", ["edge", "confidence", "volume"], index=0)
        venues = st.multiselect("Venues", ["polymarket", "kalshi"], default=["polymarket", "kalshi"])

    data = load_market_opportunities()
    _render_top_strip(data)

    opportunities = data.get("opportunities", [])
    if category != "All":
        opportunities = [m for m in opportunities if m.get("category") == category]
    if venues:
        opportunities = [m for m in opportunities if m.get("venue") in venues]
    if sort_by == "confidence":
        opportunities = sorted(opportunities, key=lambda m: m.get("confidence_pct", 0), reverse=True)
    elif sort_by == "volume":
        opportunities = sorted(opportunities, key=lambda m: m.get("volume", 0), reverse=True)
    else:
        opportunities = sorted(opportunities, key=lambda m: m.get("edge_pct", 0), reverse=True)

    hero = data.get("hero_pick")
    if hero and category != "All" and hero.get("category") != category:
        hero = opportunities[0] if opportunities else None
    elif not hero and opportunities:
        hero = opportunities[0]

    if "selected_market_id" not in st.session_state and opportunities:
        st.session_state["selected_market_id"] = opportunities[0].get("market_id")
    if "order_market_id" not in st.session_state:
        st.session_state["order_market_id"] = st.session_state.get("selected_market_id")
    if "order_side" not in st.session_state:
        st.session_state["order_side"] = "YES"

    left, center, right = st.columns([1, 2.2, 1])

    with left:
        st.markdown("##### Categories")
        for cat in categories:
            active = "→ " if cat == category else "  "
            st.markdown(f"{active}**{cat}**" if cat == category else cat)

    with center:
        if hero:
            _render_hero(hero)
        st.markdown("##### AI-Ranked Opportunities")
        for i, m in enumerate(opportunities[:8], 1):
            mid = m.get("market_id")
            selected = mid == st.session_state.get("selected_market_id")
            _render_feed_card(m, i, selected)
            if st.button(f"Select #{i}", key=f"sel_{mid}", use_container_width=True):
                st.session_state["selected_market_id"] = mid
                st.session_state["order_market_id"] = mid
                st.rerun()

        selected = get_market_by_id(data, st.session_state.get("selected_market_id", ""))
        if selected:
            st.markdown("---")
            st.markdown(f"##### {selected.get('question', '')}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Edge", f"+{selected.get('edge_pct', 0):.1f}%")
            c2.metric("Model", fmt_pct(selected.get("model_prob", 0), 0))
            c3.metric("Market", fmt_pct(selected.get("market_price", 0), 0))
            c4.metric("Payout", f"{selected.get('payout_multiplier', 0):.2f}x")
            _render_detail_chart(selected)

    with right:
        _render_portfolio(data.get("portfolio", []))
        side = st.radio("Order side", ["YES", "NO"], horizontal=True, key="ticket_side")
        st.session_state["order_side"] = side
        contracts = st.number_input("Contracts", min_value=1, max_value=10_000, value=100, step=10)
        order_market = get_market_by_id(data, st.session_state.get("order_market_id", ""))
        _render_order_ticket(order_market, side, int(contracts))
