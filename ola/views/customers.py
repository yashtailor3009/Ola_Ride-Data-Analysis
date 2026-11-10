"""Customers view - repeat behaviour, customers who never completed a ride, top customers, win-back list."""
from __future__ import annotations

import streamlit as st

from .. import charts
from .. import config as cfg
from .. import metrics as m
from ..context import AppContext
from .. import theme as ui


def render(ctx: AppContext) -> None:
    df = ctx.df
    ui.page_header("Customer behaviour", "Who books, how often, who is lost, and who to win back.", scope=ctx.scope)
    if df.empty:
        return ui.empty_state()
    c = m.customer_outcomes(df)
    ui.kpi_row([
        {"label": "Customers", "value": m.fmt_int(c["customers"]), "hint": "distinct in selection"},
        {"label": "Booked only once", "value": m.fmt_pct(c["single_booking_rate"]), "hint": "one-and-done"},
        {"label": "Repeat customers", "value": m.fmt_pct(c["repeat_rate"]), "hint": f"{m.fmt_int(c['repeat_customers'])} customers"},
        {"label": "Never completed a ride", "value": m.fmt_pct(c["never_completed_rate"]), "hint": f"{m.fmt_int(c['never_completed'])} customers",
         "color": cfg.STATUS_COLORS["Canceled by Driver"]},
    ])
    st.markdown("")
    left, right = st.columns(2)
    with left:
        ui.chart_block(charts.customer_frequency_chart(m.customer_frequency(df)), "Almost every customer books exactly once",
                       "Customers by number of bookings in the period.",
                       "Retention, not acquisition, is the growth lever.", key="cu_freq")
    with right:
        got = c["customers"] - c["never_completed"]
        ui.chart_block(charts.donut(["Completed at least one ride", "Never completed a ride"], [got, c["never_completed"]],
                                    [cfg.STATUS_COLORS["Success"], cfg.STATUS_COLORS["Canceled by Driver"]],
                                    m.fmt_pct(c["never_completed_rate"]), "never completed"),
                       "A third of customers never got a ride", "Customers split by whether any booking was completed.",
                       "These customers paid acquisition cost and received nothing: the clearest win-back pool.", key="cu_never")

    ui.section("Top customers")
    t1, t2 = st.tabs(["By number of rides", "By booking value"])
    with t1:
        st.caption("Ties on ride count are broken by completed booking value, then Customer_ID (so the answer is deterministic).")
        ui.show_table(m.top_customers_by_rides(df, 5))
    with t2:
        ui.show_table(m.top_customers_by_value(df, 5))

    ui.section("Win-back list")
    tables = m.anomaly_tables(df)
    key = [k for k in tables if k.startswith("Customers with")][0]
    win = tables[key]
    st.caption(f"{len(win):,} customers had {cfg.REPEAT_FAILURE_THRESHOLD}+ failed bookings: the first group to contact with a priority-dispatch offer.")
    ui.show_table(win.head(200))
    st.download_button("Download win-back list (CSV)", win.to_csv(index=False).encode("utf-8"), "winback_customers.csv", "text/csv")
