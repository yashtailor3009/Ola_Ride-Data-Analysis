"""
ola.theme
=========
Everything visual that is *Streamlit-specific*: global CSS, KPI cards, insight
cards, the "chart block" wrapper (headline + chart + so-what), and thin
wrappers that hide differences between Streamlit versions.

Design direction
----------------
Think "city transit map meets finance report": a deep green-black sidebar, a
pale paper canvas, white cards, and one lime accent used only where the eye
should land. Headlines state the *finding* (action titles), not the topic.
Fonts: Bricolage Grotesque (headlines, numbers) + Plus Jakarta Sans (body),
loaded from Google Fonts with system fallbacks so the app still renders offline.
"""
from __future__ import annotations

import html
from typing import Iterable

import streamlit as st

from . import config as cfg
from .metrics import Insight

# --------------------------------------------------------------------------- #
# Version-safe wrappers
# --------------------------------------------------------------------------- #
def _st_version() -> tuple[int, int]:
    """(major, minor) of the installed Streamlit, tolerant of dev/rc suffixes."""
    parts = []
    for chunk in st.__version__.split(".")[:2]:
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return (parts[0], parts[1] if len(parts) > 1 else 0)


def stretch_kwargs() -> dict:
    """Full-width option: ``width='stretch'`` on new Streamlit, ``use_container_width`` on older."""
    return {"width": "stretch"} if _st_version() >= (1, 50) else {"use_container_width": True}


PLOT_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


def show_plot(fig, key: str | None = None) -> None:
    """Render a Plotly figure full-width with a tidy mode bar."""
    st.plotly_chart(fig, key=key, config=PLOT_CONFIG, **stretch_kwargs())


def show_table(df, **kwargs) -> None:
    """Render a DataFrame full-width without the index column."""
    st.dataframe(df, hide_index=True, **stretch_kwargs(), **kwargs)


# --------------------------------------------------------------------------- #
# CSS
# --------------------------------------------------------------------------- #
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

html, body, .stApp, [class*="st-"] {{ font-family: 'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif; }}
.stApp {{ background: {cfg.PAPER}; color: {cfg.INK}; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1380px; }}

h1, h2, h3, h4 {{ font-family: 'Bricolage Grotesque', 'Plus Jakarta Sans', sans-serif; color: {cfg.INK};
                  letter-spacing: -0.02em; }}
h2 {{ font-size: 1.55rem; margin-top: 1.6rem; }}
h3 {{ font-size: 1.2rem; }}

/* ---- sidebar -------------------------------------------------------- */
[data-testid="stSidebar"] {{ background: {cfg.INK}; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span.sb-note {{ color: #E8EFE9; }}
.sb-section {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700; font-size: 0.95rem;
               color: {cfg.LIME}; margin: 1.1rem 0 0.2rem 0; }}
.sb-note {{ color: #9FB0A8; font-size: 0.78rem; line-height: 1.35; }}

/* ---- page header ---------------------------------------------------- */
.page-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1rem;
              flex-wrap: wrap; margin-bottom: 0.4rem; }}
.page-head h1 {{ margin: 0; font-size: 2.05rem; font-weight: 800; }}
.page-sub {{ color: {cfg.MUTED}; font-size: 0.95rem; margin: 0.15rem 0 0.9rem 0; max-width: 62rem; }}
.scope-chip {{ background: #FFFFFF; border: 1px solid {cfg.GRID}; border-radius: 999px; padding: 0.3rem 0.85rem;
               font-size: 0.8rem; color: {cfg.MUTED}; white-space: nowrap; }}

/* ---- KPI cards ------------------------------------------------------ */
.kpi {{ background: #FFFFFF; border: 1px solid {cfg.GRID}; border-radius: 16px; padding: 0.95rem 1.1rem 0.85rem 1.1rem;
        height: 100%; }}
.kpi-label {{ font-size: 0.78rem; color: {cfg.MUTED}; font-weight: 600; display: flex; align-items: center; gap: 0.4rem; }}
.kpi-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.kpi-value {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.9rem; font-weight: 800; line-height: 1.15;
              color: {cfg.INK}; margin-top: 0.25rem; }}
.kpi-hint {{ font-size: 0.76rem; color: {cfg.MUTED}; margin-top: 0.2rem; }}

/* ---- chart blocks --------------------------------------------------- */
div[data-testid="stVerticalBlockBorderWrapper"] {{ background: #FFFFFF; border-radius: 18px; border-color: {cfg.GRID} !important; }}
.cb-title {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.12rem; font-weight: 700; color: {cfg.INK};
             line-height: 1.25; }}
.cb-take {{ font-size: 0.86rem; color: {cfg.MUTED}; margin: 0.15rem 0 0.4rem 0; }}
.cb-sowhat {{ background: {cfg.PAPER}; border-radius: 10px; padding: 0.55rem 0.8rem; font-size: 0.84rem; color: {cfg.INK};
              margin-top: 0.3rem; }}

/* ---- insight cards -------------------------------------------------- */
.ins {{ background: #FFFFFF; border: 1px solid {cfg.GRID}; border-radius: 18px; padding: 1.1rem 1.25rem 1rem 1.25rem;
        margin-bottom: 0.9rem; }}
.ins-top {{ display: flex; justify-content: space-between; gap: 1.2rem; align-items: flex-start; }}
.ins-pill {{ display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 0.15rem 0.6rem; border-radius: 999px;
             background: {cfg.INK}; color: {cfg.LIME}; margin-right: 0.4rem; }}
.ins-conf {{ font-size: 0.72rem; color: {cfg.MUTED}; }}
.ins-title {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 1.22rem; font-weight: 700; line-height: 1.25;
              margin: 0.45rem 0 0 0; color: {cfg.INK}; }}
.ins-metric {{ text-align: right; min-width: 9.5rem; }}
.ins-metric .v {{ font-family: 'Bricolage Grotesque', sans-serif; font-size: 2rem; font-weight: 800; line-height: 1.1; color: {cfg.INK};
                  background: {cfg.LIME}; padding: 0.05rem 0.5rem; border-radius: 8px; display: inline-block; }}
.ins-metric .l {{ font-size: 0.72rem; color: {cfg.MUTED}; margin-top: 0.25rem; }}
.ins-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-top: 0.85rem; }}
@media (max-width: 900px) {{ .ins-grid {{ grid-template-columns: 1fr; }} .ins-top {{ flex-direction: column; }}
                              .ins-metric {{ text-align: left; }} }}
.ins-col h5 {{ font-size: 0.78rem; font-weight: 700; color: {cfg.MUTED}; margin: 0 0 0.25rem 0; }}
.ins-col p {{ font-size: 0.86rem; line-height: 1.5; margin: 0; color: {cfg.INK}; }}
.ins-ev {{ font-size: 0.74rem; color: {cfg.MUTED}; margin-top: 0.7rem; border-top: 1px dashed {cfg.GRID}; padding-top: 0.5rem; }}

/* ---- callouts ------------------------------------------------------- */
.callout {{ border-radius: 14px; padding: 0.8rem 1rem; font-size: 0.9rem; margin: 0.5rem 0 0.9rem 0; line-height: 1.5; }}
.callout.warn {{ background: #FFF4DD; border: 1px solid #F2D9A0; }}
.callout.info {{ background: #E9F2EC; border: 1px solid #CDE0D3; }}
.callout.bad  {{ background: #FCE9E3; border: 1px solid #F1C4B6; }}

/* ---- misc ----------------------------------------------------------- */
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; }}
code {{ font-size: 0.85em; }}
</style>
"""


def inject_css() -> None:
    """Install the global stylesheet (call once per run, right after set_page_config)."""
    st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Components
# --------------------------------------------------------------------------- #
def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def page_header(title: str, subtitle: str = "", scope: str = "") -> None:
    """Title row with an optional 'scope' chip showing the active filters."""
    chip = f"<span class='scope-chip'>{_esc(scope)}</span>" if scope else ""
    st.markdown(f"<div class='page-head'><h1>{_esc(title)}</h1>{chip}</div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='page-sub'>{_esc(subtitle)}</div>", unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f"## {title}")


def kpi_card(label: str, value: str, hint: str = "", color: str = cfg.INK) -> str:
    """HTML for one KPI card (a single line, so Markdown never treats it as a code block)."""
    return (f"<div class='kpi'><div class='kpi-label'><span class='kpi-dot' style='background:{color}'></span>{_esc(label)}</div>"
            f"<div class='kpi-value'>{_esc(value)}</div><div class='kpi-hint'>{_esc(hint)}</div></div>")


def kpi_row(items: Iterable[dict]) -> None:
    """Render KPI cards side by side. Each item: ``{label, value, hint, color}``."""
    items = list(items)
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        col.markdown(kpi_card(item["label"], item["value"], item.get("hint", ""), item.get("color", cfg.INK)),
                     unsafe_allow_html=True)


def callout(text: str, tone: str = "info") -> None:
    """Coloured note box. ``text`` may contain <b> tags (inputs are our own strings)."""
    st.markdown(f"<div class='callout {tone}'>{text}</div>", unsafe_allow_html=True)


def chart_block(fig, title: str, takeaway: str = "", so_what: str = "", key: str | None = None) -> None:
    """A bordered card: action headline, supporting line, the chart, and a 'so what'."""
    with st.container(border=True):
        st.markdown(f"<div class='cb-title'>{_esc(title)}</div>"
                    + (f"<div class='cb-take'>{_esc(takeaway)}</div>" if takeaway else ""), unsafe_allow_html=True)
        show_plot(fig, key=key)
        if so_what:
            st.markdown(f"<div class='cb-sowhat'><b>So what:</b> {_esc(so_what)}</div>", unsafe_allow_html=True)


def insight_card(ins: Insight) -> None:
    """Full What / Why / So-what card for one insight."""
    evidence = ("<div class='ins-ev'><b>Evidence:</b> " + _esc("  ·  ".join(ins.evidence)) + "</div>") if ins.evidence else ""
    st.markdown(
        "<div class='ins'>"
        f"<div class='ins-top'><div><span class='ins-pill'>{_esc(ins.category)}</span>"
        f"<span class='ins-conf'>{_esc(ins.id)} · confidence: {_esc(ins.confidence)}</span>"
        f"<div class='ins-title'>{_esc(ins.title)}</div></div>"
        f"<div class='ins-metric'><div class='v'>{_esc(ins.metric)}</div><div class='l'>{_esc(ins.metric_label)}</div></div></div>"
        "<div class='ins-grid'>"
        f"<div class='ins-col'><h5>What the data shows</h5><p>{_esc(ins.what)}</p></div>"
        f"<div class='ins-col'><h5>Why it happens</h5><p>{_esc(ins.why)}</p></div>"
        f"<div class='ins-col'><h5>What to do</h5><p>{_esc(ins.action)}</p></div>"
        f"</div>{evidence}</div>",
        unsafe_allow_html=True)


def sidebar_section(title: str, note: str = "") -> None:
    st.sidebar.markdown(f"<div class='sb-section'>{_esc(title)}</div>", unsafe_allow_html=True)
    if note:
        st.sidebar.markdown(f"<div class='sb-note'><span class='sb-note'>{_esc(note)}</span></div>", unsafe_allow_html=True)


def empty_state() -> None:
    """Shown by a view when the current filters leave no rows."""
    st.warning("No bookings match the current filters. Widen the date range or clear a filter in the sidebar.")
