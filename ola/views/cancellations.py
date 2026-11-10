"""Cancellation view - customer reasons, driver reasons, root-cause attribution, incomplete rides."""
from __future__ import annotations

import streamlit as st

from .. import charts
from .. import config as cfg
from .. import metrics as m
from ..context import AppContext
from .. import theme as ui


def render(ctx: AppContext) -> None:
    df = ctx.df
    ui.page_header("Cancellations & failures", "Why bookings do not become rides, and who is really responsible.", scope=ctx.scope)
    if df.empty:
        return ui.empty_state()
    k = m.kpis(df)
    ui.kpi_row([
        {"label": "Driver cancelled", "value": m.fmt_pct(k["driver_cancel_rate"]), "hint": "of all bookings", "color": cfg.STATUS_COLORS["Canceled by Driver"]},
        {"label": "Driver not found", "value": m.fmt_pct(k["no_driver_rate"]), "hint": "of all bookings", "color": cfg.STATUS_COLORS["Driver Not Found"]},
        {"label": "Customer cancelled", "value": m.fmt_pct(k["customer_cancel_rate"]), "hint": "of all bookings", "color": cfg.STATUS_COLORS["Canceled by Customer"]},
        {"label": "Success rate", "value": m.fmt_pct(k["success_rate"]), "hint": "the remainder", "color": cfg.STATUS_COLORS["Success"]},
    ])
    st.markdown("")

    ui.chart_block(charts.failure_attribution_chart(m.failure_attribution(df)),
                   "About 88% of failures trace back to the supply side",
                   "Every failed booking assigned to a root cause. A customer who cancels because the driver is stalled counts as driver-triggered.",
                   "Track a 'driver-attributable failure rate' as the north-star metric.", key="ca_att")

    left, right = st.columns(2)
    with left:
        ui.chart_block(charts.customer_reasons_chart(m.customer_cancel_reasons(df)), "Why customers cancel",
                       "Reasons given on 'Canceled by Customer' bookings.",
                       "More than half are reactions to driver behaviour, not customer choices.", key="ca_cust")
    with right:
        ui.chart_block(charts.driver_reasons_chart(m.driver_cancel_reasons(df)), "Why drivers cancel",
                       "Reasons given on 'Canceled by Driver' bookings.",
                       "Most cite the rider, but 'customer related issue' is too vague to act on.", key="ca_drv")

    ac = int((df["Canceled_Rides_by_Customer"] == "AC is Not working").sum())
    ac_bad = int(((df["Canceled_Rides_by_Customer"] == "AC is Not working") & df["Vehicle_Type"].isin(cfg.NON_AC_VEHICLES)).sum())
    if ac:
        ui.callout(f"<b>Data-integrity flag:</b> {ac_bad:,} of {ac:,} 'AC is not working' cancellations ({ac_bad / ac * 100:.1f}%) were logged on "
                   "Bike, eBike or Auto - vehicles that have no AC. The cancellation-reason list is not vehicle-aware.", "warn")

    ui.section("Incomplete rides")
    left, right = st.columns(2)
    inc = m.incomplete_reasons(df)
    with left:
        ui.chart_block(charts.reason_bars(inc, base_color=cfg.STATUS_COLORS["Canceled by Customer"],
                                          note="Paid rides that ended early"),
                       "Customer demand and vehicle breakdown cause 4 in 5 incomplete rides",
                       "Reasons on completed bookings flagged 'Incomplete'.",
                       "Every incomplete ride still has a payment recorded - refund and dispute exposure.", key="ca_inc")
    with right:
        done = df[df["Is_Successful"] == 1]
        rate = done.groupby("Vehicle_Type")["Incomplete_Rides"].apply(lambda s: (s == "Yes").mean() * 100).reset_index(name="Share_Pct")
        rate = rate.assign(Count=done.groupby("Vehicle_Type")["Incomplete_Rides"].apply(lambda s: int((s == "Yes").sum())).values,
                           Reason=rate["Vehicle_Type"]).sort_values("Share_Pct", ascending=False)
        ui.chart_block(charts.reason_bars(rate, label="Reason", value="Count", base_color=cfg.INK,
                                          note="Incomplete share is 5.7%-6.5% on every vehicle"),
                       "Incomplete rides are not tied to one vehicle",
                       "Number of incomplete rides per vehicle type.",
                       "A general maintenance and re-dispatch gap, not a bad vehicle model.", key="ca_inc_veh")
