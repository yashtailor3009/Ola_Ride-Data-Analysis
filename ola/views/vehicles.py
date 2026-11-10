"""Vehicle Type view - scorecard, distance, ratings, outcome mix, pricing per km, turn-around time."""
from __future__ import annotations

import streamlit as st

from .. import charts
from .. import metrics as m
from ..context import AppContext
from .. import theme as ui


def render(ctx: AppContext) -> None:
    df = ctx.df
    ui.page_header("Vehicle types", "How the seven vehicle types compare on volume, outcomes, distance, ratings and price.",
                   scope=ctx.scope)
    if df.empty:
        return ui.empty_state()

    veh = m.vehicle_summary(df)
    ui.section("Vehicle scorecard")
    cols = ["Icon", "Vehicle_Type", "Class", "Bookings", "Success_Rate_Pct", "Revenue", "Avg_Fare",
            "Avg_Distance_Km", "Avg_Customer_Rating", "Avg_Driver_Rating"]
    ui.show_table(veh[cols], column_config={
        "Icon": st.column_config.ImageColumn("", width="small"),
        "Vehicle_Type": "Vehicle",
        "Success_Rate_Pct": st.column_config.NumberColumn("Success %", format="%.1f"),
        "Revenue": st.column_config.NumberColumn("Revenue (₹)", format="%d"),
        "Avg_Fare": st.column_config.NumberColumn("Avg fare (₹)", format="%.0f"),
        "Avg_Distance_Km": st.column_config.NumberColumn("Avg km (completed)", format="%.1f"),
        "Avg_Customer_Rating": st.column_config.NumberColumn("Cust. rating", format="%.2f"),
        "Avg_Driver_Rating": st.column_config.NumberColumn("Driver rating", format="%.2f"),
    })

    left, right = st.columns(2)
    with left:
        ui.chart_block(charts.vehicle_distance_top(veh), "Top 5 vehicle types by ride distance",
                       "Total kilometres of completed rides.",
                       "Distance totals follow ride volume; Auto is excluded from the top 5 because its trips are shorter.", key="ve_dist")
    with right:
        ui.chart_block(charts.vehicle_rating(m.vehicle_ratings(df), float(df["Customer_Rating"].mean())),
                       "Average customer rating is the same for every vehicle",
                       "Mean customer rating per vehicle type.",
                       "Vehicle choice does not explain satisfaction; look at dispatch and cancellations instead.", key="ve_rating")

    left, right = st.columns(2)
    with left:
        ui.chart_block(charts.vehicle_status_mix(m.vehicle_status_mix(df)), "Every vehicle fails in the same way",
                       "How each vehicle's bookings end (100% = all its bookings).",
                       "Because the mix is identical, no vehicle-specific fix will move the success rate.", key="ve_mix")
    with right:
        ui.chart_block(charts.vehicle_fare_per_km(veh), "Auto earns 2.5x more per km than any other vehicle",
                       "Revenue per km driven on completed rides.",
                       "Fares do not scale with distance, so the short-trip Auto product yields the most per km.", key="ve_fpk")

    ui.chart_block(charts.vehicle_tat(veh), "Turn-around times are identical across vehicles",
                   "Average V_TAT (vehicle) and C_TAT (customer) on completed rides. Units are not documented in the source.",
                   "Neither TAT differs by vehicle, so speed is not a differentiator in this data.", key="ve_tat")
