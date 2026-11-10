"""Anomalies & fraud view - rule-based review queues. Flags are candidates, not proof of fraud."""
from __future__ import annotations

import streamlit as st

from .. import charts
from .. import config as cfg
from .. import metrics as m
from ..context import AppContext
from .. import theme as ui


def render(ctx: AppContext) -> None:
    df = ctx.df
    ui.page_header("Anomalies & fraud signals",
                   "Rule-based review queues for unusual bookings. A flag is a reason to look, not proof of fraud.", scope=ctx.scope)
    if df.empty:
        return ui.empty_state()
    score = m.anomaly_scorecard(df)
    tables = m.anomaly_tables(df)
    ui.chart_block(charts.anomaly_bars(score), "Where to point the review team first",
                   "Number of records flagged by each rule in the current selection.",
                   "Start with fares above INR 500/km and premium fares on very short rides - the strongest fare-inflation signatures.", key="an_bar")

    st.markdown("**Rules**")
    st.markdown(
        f"- **Pickup equals drop**: start and end area are the same.\n"
        f"- **Fare above {cfg.CURRENCY}{cfg.EXTREME_FARE_PER_KM}/km**: completed ride priced far above the ~{cfg.CURRENCY}22/km norm.\n"
        f"- **Fare >= {cfg.CURRENCY}{cfg.HIGH_FARE_SHORT_RIDE[0]:,} on a <= {cfg.HIGH_FARE_SHORT_RIDE[1]} km ride**: premium fare for a very short trip.\n"
        "- **AC complaint on a non-AC vehicle**: Bike / eBike / Auto cancelled because 'AC is not working'.\n"
        f"- **Rating gap >= {cfg.RATING_MISMATCH_GAP}**: driver and customer ratings disagree sharply.\n"
        f"- **Customers with {cfg.REPEAT_FAILURE_THRESHOLD}+ failed bookings**: repeated failure, churn and abuse risk.")

    rule = st.selectbox("Inspect a review queue", list(tables), key="an_rule")
    table = tables[rule]
    st.caption(f"{len(table):,} records. Showing the first 500.")
    ui.show_table(table.head(500))
    st.download_button("Download this queue (CSV)", table.to_csv(index=False).encode("utf-8"), "anomaly_queue.csv", "text/csv")
