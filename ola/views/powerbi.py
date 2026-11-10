"""Power BI view - embeds the published report if a URL is configured, otherwise shows the build kit."""
from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

from .. import config as cfg
from ..context import AppContext
from .. import theme as ui

PBI_DIR = cfg.ROOT_DIR / "powerbi"
PAGES = [
    ("1. Overall", "Ride Volume Over Time (line) · Booking Status Breakdown (donut) · KPI cards"),
    ("2. Vehicle Type", "Top 5 Vehicle Types by Ride Distance (bar) · Avg Customer Rating by Vehicle Type (bar) · Cancellation Rate by Vehicle"),
    ("3. Revenue", "Revenue by Payment Method (bar/donut) · Top 5 Customers by Booking Value (table/bar) · Ride Distance Distribution Per Day (box/line)"),
    ("4. Cancellation", "Cancelled Rides Reasons - Customers (bar) · Cancelled Rides Reasons - Drivers (bar) · Incomplete Rides Reasons"),
    ("5. Ratings", "Driver Ratings (histogram) · Customer Ratings (histogram) · Customer vs Driver Ratings (matrix/scatter)"),
]


def render(ctx: AppContext) -> None:
    ui.page_header("Power BI dashboard", "The same five views, built in Power BI for business users who live in Microsoft's stack.",
                   scope="Optional embed")
    if ctx.powerbi_url:
        st.caption("Embedded from your published Power BI report.")
        safe = html.escape(ctx.powerbi_url, quote=True)
        components.html(f'<iframe title="OLA Power BI" width="100%" height="720" src="{safe}" frameborder="0" allowfullscreen="true" '
                        'style="border:1px solid #E3E8DF;border-radius:14px"></iframe>', height=740)
    else:
        ui.callout("<b>No Power BI report is linked yet.</b> Build it with the kit below, publish it (<i>File → Embed report → Publish to web</i>), "
                   "then set <code>POWERBI_EMBED_URL</code> in <code>.streamlit/secrets.toml</code> (or as an environment variable) and this page will embed it.", "info")

    ui.section("The five dashboard pages")
    for name, visuals in PAGES:
        st.markdown(f"**{name}** - {visuals}")

    ui.section("Power BI build kit")
    st.caption("Everything needed to recreate the dashboard in Power BI Desktop in about an hour.")
    c1, c2, c3, c4 = st.columns(4)
    for col, (label, file, mime) in zip((c1, c2, c3, c4), [
        ("Theme (JSON)", "OLA_Theme.json", "application/json"),
        ("DAX measures", "measures.dax", "text/plain"),
        ("Power Query (M)", "power_query.m", "text/plain"),
        ("Build guide", "BUILD_GUIDE.md", "text/markdown"),
    ]):
        path = PBI_DIR / file
        if path.exists():
            col.download_button(label, path.read_bytes(), file, mime, key=f"pbi_{file}")
    csv = cfg.CLEAN_DATA_PATH
    if csv.exists():
        st.download_button("Cleaned dataset for Power BI (CSV.gz)", csv.read_bytes(), csv.name, "application/gzip", key="pbi_csv")
    st.markdown("**Connect to MySQL instead:** run `sql/ola_schema_and_cleaning.sql`, then in Power BI choose *Get data → MySQL database* "
                "and import `ola_rides`, `dim_vehicle` and `dim_payment`.")
