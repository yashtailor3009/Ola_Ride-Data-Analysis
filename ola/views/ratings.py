"""Ratings view - driver and customer rating distributions and how the two relate."""
from __future__ import annotations

import streamlit as st

from .. import charts
from .. import metrics as m
from ..context import AppContext
from .. import theme as ui


def render(ctx: AppContext) -> None:
    df = ctx.df
    ui.page_header("Ratings", "Driver and customer ratings on completed rides.", scope=ctx.scope)
    if df.empty or df["Is_Successful"].sum() == 0:
        return ui.empty_state()
    k = m.kpis(df)
    done = df[df["Is_Successful"] == 1]
    ui.kpi_row([
        {"label": "Avg driver rating", "value": f"{k['avg_driver_rating']:.2f}", "hint": "out of 5"},
        {"label": "Avg customer rating", "value": f"{k['avg_customer_rating']:.2f}", "hint": "out of 5"},
        {"label": "Rated 3.5 or lower (customer)", "value": m.fmt_pct((done["Customer_Rating"] <= 3.5).mean() * 100), "hint": "of completed rides"},
        {"label": "Lowest rating given", "value": f"{min(done['Driver_Ratings'].min(), done['Customer_Rating'].min()):.1f}", "hint": "a 3.0 floor"},
    ])
    st.markdown("")
    rd = m.rating_distribution(df)
    left, right = st.columns(2)
    with left:
        ui.chart_block(charts.rating_hist(rd, "Driver"), "Driver ratings are spread evenly from 3.0 to 5.0",
                       "Completed rides per rating value (red line = mean).",
                       "A flat distribution with a hard floor means the score cannot separate good drivers from bad ones.", key="rt_drv")
    with right:
        ui.chart_block(charts.rating_hist(rd, "Customer"), "Customer ratings look the same",
                       "Completed rides per rating value (red line = mean).",
                       "Both sides of the marketplace rate on the same compressed scale.", key="rt_cus")
    left, right = st.columns(2)
    with left:
        ui.chart_block(charts.rating_heatmap(m.rating_heatmap(df)), "Customer and driver ratings are independent",
                       "Share of rides in each driver-band x customer-band cell. A strong relationship would light up the diagonal.",
                       "If good rides earned good ratings from both sides, the diagonal would dominate.", key="rt_heat")
    with right:
        ui.chart_block(charts.vehicle_rating(m.vehicle_ratings(df), float(df["Customer_Rating"].mean())),
                       "Vehicle type does not change the rating", "Mean customer rating by vehicle type.",
                       "Differences are far too small to be statistically meaningful.", key="rt_veh")
    ui.callout("<b>Why this matters:</b> ratings show no relationship with distance, fare, turn-around time or vehicle, and the two sides' ratings are uncorrelated "
               "(r close to 0). A score that does not respond to service quality cannot safely drive driver incentives or deactivation decisions.", "info")
