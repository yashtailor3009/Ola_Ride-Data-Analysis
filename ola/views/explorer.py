"""Booking Explorer - search any Booking_ID / Customer_ID and slice the raw rows."""
from __future__ import annotations

import streamlit as st

from .. import config as cfg
from ..context import AppContext
from .. import theme as ui

SHOW_COLUMNS = ["Booking_ID", "Customer_ID", "Date", "Time", "Booking_Status", "Vehicle_Type", "Pickup_Location",
                "Drop_Location", "Booking_Value", "Ride_Distance", "Payment_Method", "Driver_Ratings", "Customer_Rating",
                "Failure_Reason", "Incomplete_Rides_Reason"]


def render(ctx: AppContext) -> None:
    ui.page_header("Booking explorer", "Search and slice individual bookings. Respects the sidebar filters.", scope=ctx.scope)
    df = ctx.df
    if df.empty:
        return ui.empty_state()
    c1, c2, c3 = st.columns([2, 1, 1])
    query = c1.text_input("Search Booking_ID or Customer_ID", placeholder="e.g. CID954071 or CNR2940424040", key="ex_search").strip()
    statuses = c2.multiselect("Status", cfg.STATUS_ORDER, key="ex_status")
    pay = c3.multiselect("Payment method", sorted(df["Payment_Method"].dropna().unique()), key="ex_pay")

    out = df
    if query:
        needle = query.lower()
        out = out[out["Booking_ID"].str.lower().str.contains(needle, regex=False) | out["Customer_ID"].str.lower().str.contains(needle, regex=False)]
    if statuses:
        out = out[out["Booking_Status"].isin(statuses)]
    if pay:
        out = out[out["Payment_Method"].isin(pay)]

    st.caption(f"{len(out):,} matching bookings. Showing the first 1,000.")
    shown = out[SHOW_COLUMNS].head(1000).copy()
    shown["Date"] = shown["Date"].dt.strftime("%Y-%m-%d")
    ui.show_table(shown)
    st.download_button("Download matching rows (CSV)", out[SHOW_COLUMNS].to_csv(index=False).encode("utf-8"), "ola_bookings_filtered.csv", "text/csv")
