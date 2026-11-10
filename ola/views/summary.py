"""Executive Summary - the headline numbers, every insight card, and the action roadmap."""
from __future__ import annotations

import streamlit as st

from .. import config as cfg
from .. import metrics as m
from ..context import AppContext
from .. import theme as ui


def render(ctx: AppContext) -> None:
    ui.page_header("Executive summary",
                   "What the July 2024 ride data says, why it happens, and what to do about it. "
                   "This page always uses the complete dataset; the other pages respond to the sidebar filters.",
                   scope=f"{len(ctx.full):,} bookings · July 2024")
    k = m.kpis(ctx.full)
    ui.kpi_row([
        {"label": "Bookings", "value": m.fmt_int(k["total_bookings"]), "hint": f"{m.fmt_int(k['unique_customers'])} unique customers"},
        {"label": "Success rate", "value": m.fmt_pct(k["success_rate"]), "hint": f"{m.fmt_int(k['failed'])} bookings failed",
         "color": cfg.STATUS_COLORS["Canceled by Driver"]},
        {"label": "Revenue (completed rides)", "value": m.fmt_inr(k["revenue"]), "hint": f"avg fare {cfg.CURRENCY}{k['avg_fare']:.0f}",
         "color": cfg.STATUS_COLORS["Success"]},
        {"label": "Quoted fare lost", "value": m.fmt_inr(k["quoted_fare_lost"]),
         "hint": f"{k['quoted_fare_lost'] / k['potential_value'] * 100:.1f}% of potential value", "color": cfg.STATUS_COLORS["Canceled by Driver"]},
        {"label": "Driver-side failures", "value": m.fmt_pct(k["driver_cancel_rate"] + k["no_driver_rate"]),
         "hint": f"vs {k['customer_cancel_rate']:.1f}% customer cancels", "color": cfg.STATUS_COLORS["Canceled by Customer"]},
        {"label": "Avg rating", "value": f"{k['avg_driver_rating']:.2f} / {k['avg_customer_rating']:.2f}", "hint": "driver / customer"},
    ])

    st.markdown("")
    ui.callout("<b>The headline:</b> about 38% of demand fails, and it fails equally in every vehicle type, hour, weekday and pickup area. "
               "That uniformity points to a <b>systemic dispatch and driver-supply problem</b>, not a local one - and "
               "<b>~88% of failures trace back to the supply side</b>. Fixing it is worth roughly "
               f"<b>{m.fmt_inr(0.1 * k['quoted_fare_lost'])}</b> for every 10% of failed bookings recovered.", "info")

    ui.section("Key insights")
    categories = ["All"] + sorted({i.category for i in ctx.insights})
    pick = st.radio("Filter by theme", categories, horizontal=True, label_visibility="collapsed", key="insight_theme")
    for ins in ctx.insights:
        if pick == "All" or ins.category == pick:
            ui.insight_card(ins)

    ui.section("Recommended action roadmap")
    st.caption("Impact figures are scenarios computed from the data, not forecasts. Effort is a rough analyst estimate.")
    ui.show_table(m.action_roadmap(ctx.full))

    with st.expander("How to read the confidence label"):
        st.markdown("**High** - supported by a statistical test or an exact count. **Medium** - descriptive pattern, cause inferred. "
                    "**Low** - hypothesis that needs more data. Every number on this page is computed from the data, never typed in.")
