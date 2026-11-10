"""
Ola Ride Insights - Streamlit entry point
=========================================
Run with:   streamlit run app.py

This file only wires things together: it loads cached data, builds the sidebar
(navigation + filters), assembles an ``AppContext`` and hands it to the chosen
view in ``ola/views``. All analytics live in ``ola/metrics.py`` and all drawing
in ``ola/charts.py`` / ``ola/theme.py``.
"""
from __future__ import annotations

import os

import streamlit as st
from PIL import Image

from ola import config as cfg
from ola import data, metrics, sql_engine
from ola import theme as ui
from ola.context import AppContext
from ola.views import (about, anomalies, cancellations, customers, explorer, overall, powerbi,
                       ratings, revenue, sql_lab, summary, vehicles)

st.set_page_config(page_title=cfg.APP_TITLE, page_icon=Image.open(cfg.ASSETS_DIR / "favicon.png"),
                   layout="wide", initial_sidebar_state="expanded")
ui.inject_css()

# Navigation: label -> view module (each exposes render(ctx)).
PAGES = {
    "Executive summary": summary,
    "Overall": overall,
    "Vehicle types": vehicles,
    "Revenue & pricing": revenue,
    "Cancellations": cancellations,
    "Ratings": ratings,
    "Customers": customers,
    "Anomalies": anomalies,
    "Booking explorer": explorer,
    "SQL lab": sql_lab,
    "Power BI": powerbi,
    "About & data": about,
}
FILTERED_PAGES = {"Overall", "Vehicle types", "Revenue & pricing", "Cancellations", "Ratings",
                  "Customers", "Anomalies", "Booking explorer"}
FILTER_KEYS = ("f_dates", "f_vehicles", "f_bands", "f_daytype", "f_pickups")


# --------------------------------------------------------------------------- #
# Cached resources
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Loading ride data...")
def load_data():
    return data.load_clean()


@st.cache_resource(show_spinner="Starting the SQL engine...")
def get_connection():
    """One locked-down in-memory SQLite database shared by all sessions."""
    return sql_engine.build_database(load_data())


@st.cache_data
def get_queries():
    return sql_engine.parse_query_library()


@st.cache_data(show_spinner="Computing insights...")
def get_insights():
    return metrics.build_insights(load_data())


@st.cache_data
def get_dq_report():
    return data.load_dq_report()


def get_powerbi_url() -> str:
    """Published Power BI embed URL from Streamlit secrets or an environment variable (optional)."""
    try:
        url = st.secrets.get("POWERBI_EMBED_URL", "")
    except Exception:                                  # no secrets file -> fall through to env var
        url = ""
    return url or os.environ.get("POWERBI_EMBED_URL", "")


def _reset_filters() -> None:
    """Callback for the 'Reset filters' button."""
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def build_sidebar(full) -> tuple[str, data.Filters]:
    """Draw the brand, navigation and filters; return (page, filters)."""
    st.sidebar.image(str(cfg.ASSETS_DIR / "logo_full_light.png"), width=215)
    ui.sidebar_section("Navigate")
    page = st.sidebar.radio("Navigate", list(PAGES), label_visibility="collapsed", key="nav")

    ui.sidebar_section("Filters", "Apply to Overall, Vehicle, Revenue, Cancellations, Ratings, Customers, Anomalies and Explorer. "
                                  "Chart headlines describe the full dataset; the numbers follow your filters.")
    lo, hi = full["Date"].min().date(), full["Date"].max().date()
    picked = st.sidebar.date_input("Date range", value=(lo, hi), min_value=lo, max_value=hi, key="f_dates")
    start, end = (picked[0], picked[1]) if isinstance(picked, (tuple, list)) and len(picked) == 2 else (lo, hi)
    vehicles_sel = st.sidebar.multiselect("Vehicle type", sorted(full["Vehicle_Type"].unique()), key="f_vehicles",
                                          placeholder="All vehicle types")
    bands_sel = st.sidebar.multiselect("Time of day", list(cfg.TIME_BANDS), key="f_bands", placeholder="All day")
    day_type = st.sidebar.radio("Days", data.DAY_TYPES, key="f_daytype")
    pickups_sel = st.sidebar.multiselect("Pickup area", sorted(full["Pickup_Location"].unique()), key="f_pickups",
                                         placeholder="All areas")
    st.sidebar.button("Reset filters", on_click=_reset_filters, key="f_reset")
    st.sidebar.markdown("<div class='sb-note' style='margin-top:1.2rem'>Data: Ola ride bookings, July 2024. "
                        "Built with Streamlit, Plotly, SQLite and pandas.</div>", unsafe_allow_html=True)
    filters = data.Filters(start=start, end=end, vehicles=tuple(vehicles_sel), time_bands=tuple(bands_sel),
                           day_type=day_type, pickups=tuple(pickups_sel))
    return page, filters


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    try:
        full = load_data()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()
    page, filters = build_sidebar(full)
    df = data.apply_filters(full, filters)
    ctx = AppContext(
        df=df, full=full, filters=filters, conn=get_connection(), queries=get_queries(),
        insights=get_insights(), dq_report=get_dq_report(), powerbi_url=get_powerbi_url(),
        scope=data.describe_filters(filters, len(df), len(full)) if page in FILTERED_PAGES else "",
    )
    PAGES[page].render(ctx)


main()
