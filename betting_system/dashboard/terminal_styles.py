"""Prediction-market trading terminal CSS and HTML helpers."""

TERMINAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.mono { font-family: 'IBM Plex Mono', monospace; }
.terminal-shell { background: #0d1117; color: #e6edf3; padding: 0; margin: -1rem -1rem 0 -1rem; }
.top-strip {
  position: sticky; top: 0; z-index: 999;
  background: #010409; border-bottom: 1px solid #21262d;
  padding: 10px 18px; display: flex; align-items: center; gap: 24px;
}
.brand { font-weight: 700; letter-spacing: 0.08em; font-size: 0.85rem; color: #58a6ff; }
.badge-live { background: #238636; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; }
.badge-fixture { background: #6e7681; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; }
.stat-block { display: flex; flex-direction: column; gap: 2px; }
.stat-label { color: #8b949e; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; }
.stat-value { font-size: 1.05rem; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
.stat-value.positive { color: #3fb950; }
.stat-value.accent { color: #58a6ff; }
.hero-card {
  background: #161b22; border: 1px solid #30363d; border-left: 3px solid #3fb950;
  border-radius: 8px; padding: 16px 18px; margin-bottom: 14px;
}
.hero-title { font-size: 1.05rem; font-weight: 700; margin-bottom: 6px; color: #f0f6fc; }
.hero-meta { color: #8b949e; font-size: 0.78rem; margin-bottom: 10px; }
.hero-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 12px 0; }
.hero-metric { background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 8px 10px; }
.hero-metric-label { color: #8b949e; font-size: 0.65rem; text-transform: uppercase; }
.hero-metric-val { font-family: 'IBM Plex Mono', monospace; font-size: 1.1rem; font-weight: 700; }
.edge-bar-wrap { background: #21262d; height: 6px; border-radius: 3px; margin-top: 8px; position: relative; overflow: hidden; }
.edge-bar-fill { background: #3fb950; height: 100%; border-radius: 3px; transition: width 0.6s ease; }
.feed-card {
  background: #161b22; border: 1px solid #21262d; border-radius: 6px;
  padding: 10px 12px; margin-bottom: 8px; cursor: pointer;
}
.feed-card:hover { border-color: #388bfd; background: #1c2128; }
.feed-card.selected { border-color: #58a6ff; border-left: 3px solid #58a6ff; }
.feed-rank { color: #484f58; font-size: 0.75rem; font-weight: 600; width: 20px; }
.feed-q { font-weight: 600; font-size: 0.88rem; color: #f0f6fc; }
.feed-tags { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.tag { background: #21262d; color: #8b949e; padding: 1px 6px; border-radius: 3px; font-size: 0.65rem; }
.tag.edge { color: #3fb950; border: 1px solid #238636; }
.tag.venue { color: #58a6ff; }
.panel-box { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; }
.panel-title { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: #8b949e; margin-bottom: 8px; font-weight: 600; }
.pos-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #21262d; font-size: 0.82rem; }
.pos-pnl { color: #3fb950; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
.rationale { color: #8b949e; font-size: 0.78rem; line-height: 1.4; margin-top: 8px; padding: 8px; background: #0d1117; border-radius: 4px; border-left: 2px solid #388bfd; }
</style>
"""


def fmt_pct(val: float, digits: int = 0) -> str:
    """Format probability as percentage string."""
    return f"{val * 100:.{digits}f}%"


def fmt_usd(val: float) -> str:
    """Format USD with commas."""
    if val >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"${val / 1_000:.1f}K"
    return f"${val:,.0f}"


def edge_bar_html(edge_pct: float, width_pct: float = 100) -> str:
    """Render edge bar HTML."""
    fill = min(max(abs(edge_pct) / 20.0 * 100, 8), 100)
    return f"""
    <div class="edge-bar-wrap" style="width:{width_pct}%">
      <div class="edge-bar-fill" style="width:{fill}%"></div>
    </div>
    """
