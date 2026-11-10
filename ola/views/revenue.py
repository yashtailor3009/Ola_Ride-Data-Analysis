"""Revenue view - payments & customers, distance per day, pricing & surge, revenue leakage."""
from __future__ import annotations

import streamlit as st

from .. import charts
from .. import config as cfg
from .. import metrics as m
from ..context import AppContext
from .. import theme as ui


def render(ctx: AppContext) -> None:
    df = ctx.df
    ui.page_header("Revenue & pricing", "Where the money comes from, who pays, how fares behave, and how much is lost to failed bookings.",
                   scope=ctx.scope)
    if df.empty:
        return ui.empty_state()
    k = m.kpis(df)
    pay = m.payment_summary(df)
    cash_share = float(pay.loc[pay["Payment_Method"] == "Cash", "Revenue_Share_Pct"].sum()) if not pay.empty else 0.0
    ui.kpi_row([
        {"label": "Revenue", "value": m.fmt_inr(k["revenue"]), "hint": "completed rides only", "color": cfg.STATUS_COLORS["Success"]},
        {"label": "Average fare", "value": f"{cfg.CURRENCY}{k['avg_fare']:.0f}", "hint": "per completed ride"},
        {"label": "Cash share of revenue", "value": m.fmt_pct(cash_share), "hint": "digital = " + m.fmt_pct(100 - cash_share), "color": cfg.PAYMENT_COLORS["Cash"]},
        {"label": "Quoted fare lost", "value": m.fmt_inr(k["quoted_fare_lost"]), "hint": "failed bookings", "color": cfg.STATUS_COLORS["Canceled by Driver"]},
    ])
    st.markdown("")

    tab_pay, tab_dist, tab_price, tab_leak = st.tabs(["Payments & customers", "Distance per day", "Pricing & surge", "Revenue leakage"])

    with tab_pay:
        left, right = st.columns(2)
        with left:
            ui.chart_block(charts.payment_revenue(pay), "Cash still carries more than half of revenue",
                           "Revenue by payment method (completed rides).",
                           "Average fare is the same for every method, so one flat digital incentive can target everyone.", key="rv_pay")
        with right:
            top = m.top_customers_by_value(df, 5)
            ui.chart_block(charts.top_customers_bar(top), "Top 5 customers by booking value",
                           "Total booking value of completed rides per customer.",
                           "The biggest customers are a rounding error: growth must come from volume and retention.", key="rv_top")
        st.markdown("**Top customers (detail)**")
        ui.show_table(top)

    with tab_dist:
        ui.chart_block(charts.distance_box_by_day(m.distance_per_day(df)), "Ride distance distribution for every day",
                       "Box = middle 50% of completed rides; whiskers = shortest and longest; line = daily mean.",
                       "The distribution is identical every day - no day is structurally different.", key="rv_box")

    with tab_price:
        done = df[df["Is_Successful"] == 1]
        stats = m.pricing_stats(df)
        callout_text = (f"<b>Pricing integrity check:</b> correlation between fare and distance is <b>{stats['fare_distance_corr']:.3f}</b>. "
                        "In a distance-based tariff it would be strongly positive. Either Booking_Value is not the metered fare, or the fare engine ignores distance.")
        ui.callout(callout_text, "warn")
        left, right = st.columns(2)
        with left:
            sample = done.sample(min(4000, len(done)), random_state=7) if len(done) else done
            ui.chart_block(charts.fare_vs_distance(sample, stats["fare_distance_corr"]), "Fare is unrelated to distance",
                           "4,000 randomly sampled completed rides.", "Audit the fare engine before relying on Booking_Value for pricing.", key="rv_scatter")
        with right:
            ui.chart_block(charts.distance_band_fare(m.distance_band_summary(df)), "Average fare is flat, so price per km collapses on long rides",
                           "Average fare and fare per km by distance band.", "Long-distance riders pay far less per km than short-distance riders.", key="rv_band")
        left, right = st.columns(2)
        with left:
            ui.chart_block(charts.fare_tiers_chart(m.fare_tiers(df)), "A few high fares carry a large share of revenue",
                           "Share of rides vs share of revenue by fare tier.", "Protect and review the premium-fare tier - it is heavily weighted.", key="rv_tiers")
        with right:
            ui.chart_block(charts.fare_per_km_hourly(m.fare_per_km_hourly(df)), "Surge check: price does not respond to the hour",
                           "Weighted fare per km by hour of day (no surge multiplier exists in the data).",
                           "Surge effectiveness cannot be demonstrated; add a surge-multiplier field to measure it.", key="rv_surge")

    with tab_leak:
        ui.chart_block(charts.revenue_waterfall(k, m.revenue_leakage(df)), "Failed bookings cost more than a third of potential value",
                       "From the quoted value of all bookings down to realised revenue.",
                       "Driver cancellations are the largest single leak; start recovery there.", key="rv_leak")
        leak = m.revenue_leakage(df)
        st.markdown("**Leakage detail**")
        ui.show_table(leak, column_config={
            "Quoted_Fare_Lost": st.column_config.NumberColumn("Quoted fare lost (₹)", format="%d"),
            "Share_Of_Loss_Pct": st.column_config.NumberColumn("Share of loss %", format="%.1f")})
