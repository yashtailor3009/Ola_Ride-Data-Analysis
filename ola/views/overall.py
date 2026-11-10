"""Overall view - ride volume over time, booking status breakdown, demand by hour/weekday/location."""
from __future__ import annotations

import streamlit as st

from .. import charts
from .. import config as cfg
from .. import metrics as m
from ..context import AppContext
from .. import theme as ui


def render(ctx: AppContext) -> None:
    df = ctx.df
    ui.page_header("Overall performance", "Volume, outcomes and demand patterns across the selected bookings.",
                   scope=ctx.scope)
    if df.empty:
        return ui.empty_state()

    k = m.kpis(df)
    ui.kpi_row([
        {"label": "Bookings", "value": m.fmt_int(k["total_bookings"]), "hint": f"{k['total_bookings'] / max(df['Date'].nunique(), 1):,.0f} per day"},
        {"label": "Success rate", "value": m.fmt_pct(k["success_rate"]), "hint": f"{m.fmt_int(k['completed'])} completed", "color": cfg.STATUS_COLORS["Success"]},
        {"label": "Revenue", "value": m.fmt_inr(k["revenue"]), "hint": f"{cfg.CURRENCY}{k['avg_fare']:.0f} average fare", "color": cfg.STATUS_COLORS["Success"]},
        {"label": "Quoted fare lost", "value": m.fmt_inr(k["quoted_fare_lost"]), "hint": "failed bookings", "color": cfg.STATUS_COLORS["Canceled by Driver"]},
        {"label": "Avg ride distance", "value": f"{k['avg_distance']:.1f} km", "hint": "completed rides"},
    ])
    st.markdown("")

    left, right = st.columns([2, 1])
    with left:
        ui.chart_block(charts.ride_volume(m.daily_volume(df)), "Demand is steady: about 3,300 bookings every day",
                       "Daily bookings split into completed and failed, with the 7-day average.",
                       "There is no growth or seasonality to plan around inside July; the lever is conversion, not demand.", key="ov_volume")
    with right:
        status = m.status_breakdown(df)
        ui.chart_block(charts.status_donut(status), "Only 62% of bookings end in a ride",
                       "Booking status breakdown.", "Driver cancellations alone (red) are bigger than customer cancellations.", key="ov_status")

    left, right = st.columns(2)
    with left:
        ui.chart_block(charts.hourly_demand(m.hourly_demand(df)), "No rush-hour peak: every hour looks the same",
                       "Bookings and success rate by hour of day.",
                       "Hour-based driver reallocation is not supported by this data.", key="ov_hour")
    with right:
        ui.chart_block(charts.weekday_demand(m.weekday_demand(df)), "The Monday-Wednesday 'peak' is a calendar artefact",
                       "Raw weekday totals versus average bookings per calendar day.",
                       "Always normalise per day before reading weekday patterns.", key="ov_weekday")

    ui.section("Where demand comes from")
    kind = st.radio("Location type", ["Pickup", "Drop"], horizontal=True, key="ov_loc_kind", label_visibility="collapsed")
    col = "Pickup_Location" if kind == "Pickup" else "Drop_Location"
    ui.chart_block(charts.location_bars(m.location_summary(df, col)), f"Top 10 {kind.lower()} areas look alike",
                   "Bookings per area with each area's success rate.",
                   "No area is a genuine failure hotspot; differences are within chance.", key="ov_loc")
