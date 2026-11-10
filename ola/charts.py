"""
ola.charts
==========
Plotly figure builders. Each function takes a *prepared table* from
``ola.metrics`` and returns a ``plotly.graph_objects.Figure``.

Design rules applied to every chart
-----------------------------------
* Axis titles with units (never a bare axis).
* Direct data labels where there are few bars; hover for the rest.
* One computed **annotation** that points at the thing the viewer should notice
  (peak day, average line, the 5-vs-4 weekday artefact, the 2.5x Auto gap ...).
* Brand palette from ``ola.config``; one stable colour per vehicle / status / payment.
* No titles inside the figure - the page supplies a takeaway headline above it
  (see ``ola.theme.chart_block``), so titles are never duplicated.

Only ``plotly.graph_objects`` is used (no ``plotly.express``) to keep behaviour
identical across Plotly 5.x and 6.x.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import config as cfg

FONT = "Plus Jakarta Sans, Inter, Segoe UI, Arial, sans-serif"
TRANSPARENT = "rgba(0,0,0,0)"


# =========================================================================== #
# Shared helpers
# =========================================================================== #
def _base(fig: go.Figure, height: int = 360, legend: bool = True,
          margin: dict | None = None) -> go.Figure:
    """Apply the shared layout (fonts, grid, legend, hover) to a figure."""
    fig.update_layout(
        height=height,
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor=TRANSPARENT,
        font=dict(family=FONT, size=12, color=cfg.INK),
        margin=margin or dict(l=10, r=10, t=36, b=10),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11)),
        hoverlabel=dict(bgcolor=cfg.INK, font=dict(color="#FFFFFF", family=FONT, size=12)),
    )
    fig.update_xaxes(showgrid=False, linecolor=cfg.GRID, tickfont=dict(size=11), automargin=True)
    fig.update_yaxes(gridcolor=cfg.GRID, zeroline=False, tickfont=dict(size=11), automargin=True)
    return fig


def _note(fig: go.Figure, text: str, x: float = 0.01, y: float = 0.98,
          xanchor: str = "left", yanchor: str = "top") -> None:
    """Boxed takeaway annotation anchored to the plot area (paper coordinates)."""
    fig.add_annotation(
        xref="paper", yref="paper", x=x, y=y, text=text, showarrow=False, align="left",
        xanchor=xanchor, yanchor=yanchor, bgcolor="rgba(255,255,255,0.92)", bordercolor=cfg.GRID,
        borderwidth=1, borderpad=6, font=dict(size=11, color=cfg.INK),
    )


def _callout(fig: go.Figure, x, y, text: str, ax: int = 0, ay: int = -42, yref: str = "y") -> None:
    """Arrow + label pointing at one data point."""
    fig.add_annotation(
        x=x, y=y, yref=yref, text=text, showarrow=True, arrowhead=2, arrowwidth=1.2, arrowcolor=cfg.INK,
        ax=ax, ay=ay, bgcolor=cfg.INK, bordercolor=cfg.INK, borderpad=4,
        font=dict(size=11, color="#FFFFFF"),
    )


def _date_str(series: pd.Series) -> list[str]:
    return pd.to_datetime(series).dt.strftime("%Y-%m-%d").tolist()


def _inr(v: float) -> str:
    return f"{cfg.CURRENCY}{v / 1e6:.2f}M" if abs(v) >= 1e6 else f"{cfg.CURRENCY}{v:,.0f}"


def empty_figure(message: str = "No data for the current filters") -> go.Figure:
    """Friendly placeholder when a filter leaves no rows."""
    fig = go.Figure()
    fig.add_annotation(text=message, xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                       font=dict(size=14, color=cfg.MUTED))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _base(fig, height=260, legend=False)


# =========================================================================== #
# Overall
# =========================================================================== #
def ride_volume(daily: pd.DataFrame) -> go.Figure:
    """Daily bookings stacked by outcome + 7-day average (Power BI: Ride Volume Over Time)."""
    if daily.empty:
        return empty_figure()
    x = _date_str(daily["Date"])
    fig = go.Figure()
    fig.add_bar(x=x, y=daily["Completed"], name="Completed", marker_color=cfg.STATUS_COLORS["Success"],
                hovertemplate="%{x|%d %b}<br>Completed: %{y:,}<extra></extra>")
    fig.add_bar(x=x, y=daily["Failed"], name="Failed (cancelled / no driver)", marker_color=cfg.STATUS_COLORS["Canceled by Driver"],
                opacity=0.85, hovertemplate="%{x|%d %b}<br>Failed: %{y:,}<extra></extra>")
    fig.add_scatter(x=x, y=daily["Bookings_7d_Avg"], name="7-day average", mode="lines",
                    line=dict(color=cfg.INK, width=2.5), hovertemplate="7-day avg: %{y:,.0f}<extra></extra>")
    _base(fig, height=380)
    fig.update_layout(barmode="stack", bargap=0.18, hovermode="x unified")
    fig.update_xaxes(type="date", tickformat="%d %b")
    fig.update_yaxes(title=dict(text="Bookings per day"), rangemode="tozero")
    peak, low = daily.loc[daily["Bookings"].idxmax()], daily.loc[daily["Bookings"].idxmin()]
    _callout(fig, str(peak["Date"])[:10], peak["Bookings"], f"Peak {int(peak['Bookings']):,}", ay=-30)
    _callout(fig, str(low["Date"])[:10], low["Bookings"], f"Low {int(low['Bookings']):,}", ay=-30)
    spread = (daily["Bookings"].std() / daily["Bookings"].mean() * 100) if len(daily) > 1 else 0
    _note(fig, f"Average {daily['Bookings'].mean():,.0f} bookings/day, variation only {spread:.1f}%<br>No growth or decay trend inside the month",
          x=0.01, y=0.06, yanchor="bottom")
    return fig


def donut(labels: list[str], values: list[float], colors: list[str], center_title: str,
          center_sub: str = "", height: int = 340) -> go.Figure:
    """Generic donut with a centre label (used for status split and customer outcome)."""
    if not len(values) or sum(values) == 0:
        return empty_figure()
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62, sort=False, direction="clockwise",
        marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
        textinfo="percent", textfont=dict(size=12, color="#FFFFFF"),
        hovertemplate="%{label}<br>%{value:,} (%{percent})<extra></extra>",
    ))
    _base(fig, height=height, margin=dict(l=10, r=10, t=10, b=10))
    fig.update_layout(legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02))
    fig.add_annotation(text=f"<span style='font-size:26px'><b>{center_title}</b></span><br><span style='font-size:12px;color:{cfg.MUTED}'>{center_sub}</span>",
                       x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    return fig


def status_donut(status: pd.DataFrame) -> go.Figure:
    """Booking status breakdown (Power BI: Booking Status Breakdown)."""
    total = int(status["Bookings"].sum()) if not status.empty else 0
    return donut(status["Booking_Status"].tolist(), status["Bookings"].tolist(),
                 [cfg.STATUS_COLORS[s] for s in status["Booking_Status"]], f"{total:,}", "bookings")


def hourly_demand(hr: pd.DataFrame) -> go.Figure:
    """Bookings by hour with success-rate line - the peak-hour test."""
    if hr.empty:
        return empty_figure()
    avg = hr["Bookings"].mean()
    fig = go.Figure()
    fig.add_bar(x=hr["Ride_Hour"], y=hr["Bookings"], name="Bookings", marker_color=cfg.INK, opacity=0.88,
                hovertemplate="Hour %{x}:00<br>Bookings: %{y:,}<extra></extra>")
    fig.add_scatter(x=hr["Ride_Hour"], y=hr["Success_Rate_Pct"], name="Success rate (%)", mode="lines+markers",
                    yaxis="y2", line=dict(color=cfg.STATUS_COLORS["Success"], width=2.5), marker=dict(size=6),
                    hovertemplate="Success: %{y:.1f}%<extra></extra>")
    _base(fig, height=360)
    fig.update_layout(
        yaxis=dict(title=dict(text="Bookings in the hour"), rangemode="tozero"),
        yaxis2=dict(title=dict(text="Success rate (%)"), overlaying="y", side="right", showgrid=False, range=[0, 100]),
        xaxis=dict(title=dict(text="Hour of day (0 = midnight)"), dtick=2),
    )
    fig.add_hline(y=avg, line_dash="dot", line_color=cfg.LIME, line_width=2)
    hi, lo = hr["Bookings"].max(), hr["Bookings"].min()
    _note(fig, f"Every hour is within {max(hi / avg - 1, 1 - lo / avg) * 100:.1f}% of the {avg:,.0f} average<br>No rush-hour peak to staff for",
          x=0.01, y=0.30, yanchor="top")
    return fig


def weekday_demand(wd: pd.DataFrame) -> go.Figure:
    """Raw totals vs per-day averages - exposes the 5-vs-4 calendar artefact."""
    if wd.empty:
        return empty_figure()
    names = [n[:3] for n in wd["Day_Name"]]
    fig = go.Figure()
    fig.add_bar(x=names, y=wd["Total_Bookings"], name="Total bookings in July", marker_color="#C9D2CC",
                text=[f"{v:,}" for v in wd["Total_Bookings"]], textposition="outside", cliponaxis=False,
                hovertemplate="%{x}<br>Total: %{y:,}<extra></extra>")
    fig.add_scatter(x=names, y=wd["Avg_Bookings_Per_Day"], name="Average per calendar day", mode="markers+lines",
                    yaxis="y2", marker=dict(color=cfg.INK, size=11, symbol="diamond"), line=dict(color=cfg.INK, width=1.5, dash="dot"),
                    hovertemplate="%{x}<br>Per day: %{y:,.0f}<extra></extra>")
    _base(fig, height=360)
    top = wd["Total_Bookings"].max() * 1.25
    ymax2 = top / wd["Calendar_Days"].min()
    fig.update_layout(
        yaxis=dict(title=dict(text="Total bookings"), range=[0, top]),
        yaxis2=dict(title=dict(text="Bookings per calendar day"), overlaying="y", side="right", showgrid=False, range=[0, ymax2]),
    )
    _note(fig, "Mon-Wed look busier only because July 2024<br>had <b>5</b> of each; the others had <b>4</b>.<br>Per-day average (diamonds) is flat.",
          x=0.99, y=0.99, xanchor="right")
    return fig


def location_bars(loc: pd.DataFrame, n: int = 10) -> go.Figure:
    """Top pickup locations by demand, labelled with their success rate."""
    if loc.empty:
        return empty_figure()
    top = loc.head(n).iloc[::-1]
    avg_succ = loc["Completed"].sum() / loc["Bookings"].sum() * 100
    fig = go.Figure(go.Bar(
        y=top.iloc[:, 0], x=top["Bookings"], orientation="h", marker_color=cfg.INK, opacity=0.9,
        text=[f"{b:,}  ·  {s:.1f}% success" for b, s in zip(top["Bookings"], top["Success_Rate_Pct"])],
        textposition="outside", cliponaxis=False, hovertemplate="%{y}<br>Bookings: %{x:,}<extra></extra>"))
    _base(fig, height=380, legend=False, margin=dict(l=10, r=90, t=20, b=10))
    fig.update_xaxes(title=dict(text="Bookings"), range=[0, top["Bookings"].max() * 1.35])
    fig.update_yaxes(showgrid=False)
    _note(fig, f"Network success rate {avg_succ:.1f}%<br>Locations differ by chance only", x=0.99, y=0.04, xanchor="right", yanchor="bottom")
    return fig


# =========================================================================== #
# Vehicles
# =========================================================================== #
def vehicle_distance_top(veh: pd.DataFrame, n: int = 5) -> go.Figure:
    """Top vehicle types by total completed distance (Power BI: Top 5 Vehicle Types by Ride Distance)."""
    if veh.empty:
        return empty_figure()
    top = veh.sort_values("Total_Distance_Km", ascending=False).head(n).iloc[::-1]
    fig = go.Figure(go.Bar(
        y=top["Vehicle_Type"], x=top["Total_Distance_Km"], orientation="h",
        marker_color=[cfg.VEHICLE_COLORS[v] for v in top["Vehicle_Type"]],
        text=[f"{d / 1000:,.1f}K km  ·  avg {a:.1f} km/ride" for d, a in zip(top["Total_Distance_Km"], top["Avg_Distance_Km"])],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>Total distance: %{x:,.0f} km<extra></extra>"))
    _base(fig, height=340, legend=False, margin=dict(l=10, r=120, t=20, b=10))
    fig.update_xaxes(title=dict(text="Total distance of completed rides (km)"), range=[0, top["Total_Distance_Km"].max() * 1.45])
    fig.update_yaxes(showgrid=False)
    lead, last = top["Total_Distance_Km"].max(), top["Total_Distance_Km"].min()
    _note(fig, f"Top 5 are within {(lead / last - 1) * 100:.1f}% of each other<br>Distance follows ride volume, not vehicle choice",
          x=0.99, y=0.04, xanchor="right", yanchor="bottom")
    return fig


def vehicle_rating(vr: pd.DataFrame, overall: float | None = None) -> go.Figure:
    """Average customer rating per vehicle type (Power BI: Average Customer Ratings by Vehicle Type)."""
    if vr.empty:
        return empty_figure()
    overall = overall if overall is not None else float(vr["Avg_Customer_Rating"].mean())
    fig = go.Figure(go.Bar(
        x=vr["Vehicle_Type"], y=vr["Avg_Customer_Rating"], marker_color=[cfg.VEHICLE_COLORS[v] for v in vr["Vehicle_Type"]],
        text=[f"{v:.2f}" for v in vr["Avg_Customer_Rating"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>Avg customer rating: %{y:.3f}<extra></extra>"))
    _base(fig, height=340, legend=False)
    fig.update_yaxes(title=dict(text="Average customer rating (1-5)"), range=[0, 5.4])
    fig.add_hline(y=overall, line_dash="dot", line_color=cfg.MUTED)
    spread = vr["Avg_Customer_Rating"].max() - vr["Avg_Customer_Rating"].min()
    _note(fig, f"Spread across vehicles: {spread:.2f} points<br>Not statistically significant", x=0.99, y=0.99, xanchor="right")
    return fig


def vehicle_status_mix(mix: pd.DataFrame) -> go.Figure:
    """100% stacked bars: how each vehicle's bookings end."""
    if mix.empty:
        return empty_figure()
    m = mix.iloc[::-1]
    fig = go.Figure()
    for status in cfg.STATUS_ORDER:
        fig.add_bar(y=m["Vehicle_Type"], x=m[status], name=status, orientation="h", marker_color=cfg.STATUS_COLORS[status],
                    text=[f"{v:.0f}%" for v in m[status]], textposition="inside", insidetextanchor="middle",
                    textfont=dict(color="#FFFFFF", size=11), hovertemplate="%{y}<br>" + status + ": %{x:.1f}%<extra></extra>")
    _base(fig, height=380, margin=dict(l=10, r=10, t=44, b=10))
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title=dict(text="Share of the vehicle's bookings (%)"), range=[0, 100])
    fig.update_yaxes(showgrid=False)
    return fig


def vehicle_fare_per_km(veh: pd.DataFrame) -> go.Figure:
    """Fare per km by vehicle - Auto's 2.5x gap."""
    if veh.empty:
        return empty_figure()
    v = veh.sort_values("Fare_Per_Km", ascending=False)
    fig = go.Figure(go.Bar(
        x=v["Vehicle_Type"], y=v["Fare_Per_Km"], marker_color=[cfg.VEHICLE_COLORS[t] for t in v["Vehicle_Type"]],
        text=[f"{cfg.CURRENCY}{x:.0f}" for x in v["Fare_Per_Km"]], textposition="outside", cliponaxis=False,
        customdata=np.stack([v["Avg_Fare"], v["Avg_Distance_Km"]], axis=-1),
        hovertemplate="%{x}<br>Fare per km: ₹%{y:.1f}<br>Avg fare: ₹%{customdata[0]:.0f}<br>Avg distance: %{customdata[1]:.1f} km<extra></extra>"))
    _base(fig, height=340, legend=False)
    fig.update_yaxes(title=dict(text="Revenue per km driven (₹)"), range=[0, v["Fare_Per_Km"].max() * 1.25])
    if "Auto" in set(v["Vehicle_Type"]) and len(v) > 1:
        auto = float(v.loc[v["Vehicle_Type"] == "Auto", "Fare_Per_Km"].iloc[0])
        rest = float(v.loc[v["Vehicle_Type"] != "Auto", "Fare_Per_Km"].mean())
        _note(fig, f"Auto earns {auto / rest:.1f}x more per km: same ~₹550 fare,<br>but trips are only ~10 km instead of ~25 km", x=0.99, y=0.99, xanchor="right")
    return fig


def vehicle_tat(veh: pd.DataFrame) -> go.Figure:
    """Average vehicle and customer turn-around time by vehicle."""
    if veh.empty:
        return empty_figure()
    v = veh.sort_values("Vehicle_Type")
    fig = go.Figure()
    fig.add_bar(x=v["Vehicle_Type"], y=v["Avg_V_TAT"], name="V_TAT (vehicle)", marker_color=cfg.INK,
                text=[f"{x:.0f}" for x in v["Avg_V_TAT"]], textposition="outside")
    fig.add_bar(x=v["Vehicle_Type"], y=v["Avg_C_TAT"], name="C_TAT (customer)", marker_color=cfg.LIME,
                text=[f"{x:.0f}" for x in v["Avg_C_TAT"]], textposition="outside")
    _base(fig, height=340)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title=dict(text="Average turn-around time (units as provided)"), range=[0, v["Avg_V_TAT"].max() * 1.2])
    return fig


# =========================================================================== #
# Revenue, pricing, customers
# =========================================================================== #
def payment_revenue(pay: pd.DataFrame) -> go.Figure:
    """Revenue by payment method (Power BI: Revenue by Payment Method)."""
    if pay.empty:
        return empty_figure()
    fig = go.Figure(go.Bar(
        x=pay["Payment_Method"], y=pay["Revenue"], marker_color=[cfg.PAYMENT_COLORS.get(p, cfg.MUTED) for p in pay["Payment_Method"]],
        text=[f"{_inr(r)}<br>{s:.1f}%" for r, s in zip(pay["Revenue"], pay["Revenue_Share_Pct"])],
        textposition="outside", cliponaxis=False, hovertemplate="%{x}<br>Revenue: ₹%{y:,.0f}<extra></extra>"))
    _base(fig, height=360, legend=False)
    fig.update_yaxes(title=dict(text="Revenue from completed rides (₹)"), range=[0, pay["Revenue"].max() * 1.3])
    digital = pay.loc[pay["Payment_Method"] != "Cash", "Revenue_Share_Pct"].sum()
    _note(fig, f"Digital methods = {digital:.1f}% of revenue<br>Average fare is the same for every method", x=0.99, y=0.99, xanchor="right")
    return fig


def top_customers_bar(top: pd.DataFrame) -> go.Figure:
    """Top customers by booking value (Power BI: Top 5 Customers by Total Booking Value)."""
    if top.empty:
        return empty_figure()
    t = top.iloc[::-1]
    fig = go.Figure(go.Bar(
        y=t["Customer_ID"], x=t["Total_Booking_Value"], orientation="h", marker_color=cfg.INK,
        text=[f"₹{v:,.0f}  ·  {r} ride{'s' if r > 1 else ''}" for v, r in zip(t["Total_Booking_Value"], t["Completed_Rides"])],
        textposition="outside", cliponaxis=False, hovertemplate="%{y}<br>Booking value: ₹%{x:,.0f}<extra></extra>"))
    _base(fig, height=300, legend=False, margin=dict(l=10, r=100, t=20, b=10))
    fig.update_xaxes(title=dict(text="Total booking value, completed rides (₹)"), range=[0, t["Total_Booking_Value"].max() * 1.35])
    fig.update_yaxes(showgrid=False)
    _note(fig, f"These {len(t)} customers = {t['Share_Of_Revenue_Pct'].sum():.2f}% of revenue<br>No key accounts to protect", x=0.99, y=0.04, xanchor="right", yanchor="bottom")
    return fig


def distance_box_by_day(dpd: pd.DataFrame) -> go.Figure:
    """Ride-distance distribution for every day (Power BI: Ride Distance Distribution Per Day).

    Box statistics are pre-computed so the chart stays light (41k points would bloat the page).
    """
    if dpd.empty:
        return empty_figure()
    x = _date_str(dpd["Date"])
    fig = go.Figure(go.Box(
        x=x, q1=dpd["Q1"].tolist(), median=dpd["Median"].tolist(), q3=dpd["Q3"].tolist(),
        lowerfence=dpd["Min"].tolist(), upperfence=dpd["Max"].tolist(), mean=dpd["Mean"].tolist(),
        marker_color=cfg.INK, fillcolor="rgba(198,226,42,0.55)", line=dict(color=cfg.INK, width=1.2),
        boxmean=False, name="Distance distribution", showlegend=False))
    fig.add_scatter(x=x, y=dpd["Mean"], mode="lines", name="Daily mean", line=dict(color=cfg.STATUS_COLORS["Canceled by Driver"], width=2))
    _base(fig, height=380)
    fig.update_xaxes(type="date", tickformat="%d %b")
    fig.update_yaxes(title=dict(text="Ride distance (km)"), rangemode="tozero")
    _note(fig, f"Daily mean stays between {dpd['Mean'].min():.1f} and {dpd['Mean'].max():.1f} km<br>Box = middle 50% of rides, whiskers = min-max",
          x=0.01, y=0.06, yanchor="bottom")
    return fig


def fare_vs_distance(sample: pd.DataFrame, corr: float) -> go.Figure:
    """Scatter of fare vs distance - a 'no relationship' cloud is the finding."""
    if sample.empty:
        return empty_figure()
    fig = go.Figure(go.Scattergl(
        x=sample["Ride_Distance"], y=sample["Booking_Value"], mode="markers",
        marker=dict(size=5, color=cfg.INK, opacity=0.28), name="Completed rides",
        hovertemplate="%{x} km → ₹%{y:,}<extra></extra>"))
    _base(fig, height=380, legend=False)
    fig.update_xaxes(title=dict(text="Ride distance (km)"))
    fig.update_yaxes(title=dict(text="Fare (₹)"), rangemode="tozero")
    _note(fig, f"Correlation = {corr:.3f}<br>A 3 km ride can cost as much as a 45 km ride", x=0.99, y=0.99, xanchor="right")
    return fig


def distance_band_fare(bands: pd.DataFrame) -> go.Figure:
    """Average fare is flat across distance bands while fare per km collapses."""
    if bands.empty:
        return empty_figure()
    fig = go.Figure()
    fig.add_bar(x=bands["Distance_Band"], y=bands["Avg_Fare"], name="Average fare (₹)", marker_color=cfg.INK, opacity=0.9,
                text=[f"₹{v:.0f}" for v in bands["Avg_Fare"]], textposition="outside", cliponaxis=False)
    fig.add_scatter(x=bands["Distance_Band"], y=bands["Fare_Per_Km"], name="Fare per km (₹)", yaxis="y2", mode="lines+markers+text",
                    line=dict(color=cfg.STATUS_COLORS["Canceled by Driver"], width=2.5), text=[f"₹{v:.0f}/km" for v in bands["Fare_Per_Km"]],
                    textposition="top center", hovertemplate="%{x}<br>₹%{y:.1f} per km<extra></extra>")
    _base(fig, height=380)
    fig.update_layout(
        yaxis=dict(title=dict(text="Average fare (₹)"), range=[0, bands["Avg_Fare"].max() * 1.5]),
        yaxis2=dict(title=dict(text="Fare per km (₹)"), overlaying="y", side="right", showgrid=False, rangemode="tozero"),
    )
    _note(fig, "Fare barely changes with distance<br>so price per km falls ~15x from short to long rides", x=0.50, y=0.99, xanchor="center")
    return fig


def fare_tiers_chart(tiers: pd.DataFrame) -> go.Figure:
    """Share of rides vs share of revenue by fare tier (heavy-tail view)."""
    if tiers.empty:
        return empty_figure()
    fig = go.Figure()
    fig.add_bar(x=tiers["Fare_Tier"].astype(str), y=tiers["Ride_Share_Pct"], name="Share of rides", marker_color="#C9D2CC",
                text=[f"{v:.1f}%" for v in tiers["Ride_Share_Pct"]], textposition="outside", cliponaxis=False)
    fig.add_bar(x=tiers["Fare_Tier"].astype(str), y=tiers["Revenue_Share_Pct"], name="Share of revenue", marker_color=cfg.INK,
                text=[f"{v:.1f}%" for v in tiers["Revenue_Share_Pct"]], textposition="outside", cliponaxis=False)
    _base(fig, height=340)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title=dict(text="Share (%)"), range=[0, max(tiers["Revenue_Share_Pct"].max(), tiers["Ride_Share_Pct"].max()) * 1.25])
    fig.update_xaxes(title=dict(text="Fare tier (₹)"))
    top = tiers.iloc[-1]
    _note(fig, f"Fares of ₹1,500+ are {top['Ride_Share_Pct']:.1f}% of rides<br>but {top['Revenue_Share_Pct']:.1f}% of revenue", x=0.01, y=0.99)
    return fig


def fare_per_km_hourly(fpk: pd.DataFrame) -> go.Figure:
    """Surge proxy: weighted fare per km by hour."""
    if fpk.empty:
        return empty_figure()
    fig = go.Figure(go.Scatter(
        x=fpk["Ride_Hour"], y=fpk["Fare_Per_Km"], mode="lines+markers", line=dict(color=cfg.INK, width=2.5),
        marker=dict(size=7), hovertemplate="Hour %{x}:00<br>₹%{y:.1f} per km<extra></extra>", name="Fare per km"))
    _base(fig, height=320, legend=False)
    fig.update_xaxes(title=dict(text="Hour of day"), dtick=2)
    fig.update_yaxes(title=dict(text="Fare per km (₹)"), range=[0, fpk["Fare_Per_Km"].max() * 1.5])
    _note(fig, f"Stays within ₹{fpk['Fare_Per_Km'].min():.1f}-₹{fpk['Fare_Per_Km'].max():.1f}/km all day<br>No visible surge response to demand", x=0.01, y=0.99)
    return fig


def revenue_waterfall(kpi: dict, leak: pd.DataFrame) -> go.Figure:
    """Potential booking value -> realised revenue, step by step (stacked-bar waterfall)."""
    if leak.empty:
        return empty_figure()
    order = ["Driver cancellation", "Customer cancellation", "No driver found"]
    leak = leak.set_index("Failure_Type").reindex(order).fillna(0)
    labels = ["Quoted value of all bookings"] + [f"Lost: {o.lower()}" for o in order] + ["Realised revenue"]
    drops = leak["Quoted_Fare_Lost"].tolist()
    potential = kpi["potential_value"]
    base, vis, colors, text = [0], [potential], [cfg.INK], [_inr(potential)]
    running = potential
    for d in drops:
        running -= d
        base.append(running)
        vis.append(d)
        colors.append(cfg.STATUS_COLORS["Canceled by Driver"])
        text.append(f"-{_inr(d)}")
    base.append(0)
    vis.append(kpi["revenue"])
    colors.append(cfg.STATUS_COLORS["Success"])
    text.append(_inr(kpi["revenue"]))
    fig = go.Figure()
    fig.add_bar(x=labels, y=base, marker_color=TRANSPARENT, hoverinfo="skip", showlegend=False)
    fig.add_bar(x=labels, y=vis, marker_color=colors, text=text, textposition="outside", cliponaxis=False,
                showlegend=False, hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>")
    _base(fig, height=380, legend=False)
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title=dict(text="Booking value (₹)"), range=[0, potential * 1.18])
    _note(fig, f"{kpi['quoted_fare_lost'] / max(potential, 1) * 100:.1f}% of quoted value never converts<br>"
               f"Recovering 10% of it = +{_inr(kpi['quoted_fare_lost'] * 0.1)}", x=0.99, y=0.99, xanchor="right")
    return fig


# =========================================================================== #
# Cancellations
# =========================================================================== #
def reason_bars(df: pd.DataFrame, label: str = "Reason", value: str = "Count", color_flag: str | None = None,
                flag_color: str | None = None, base_color: str | None = None, note: str | None = None,
                height: int = 330) -> go.Figure:
    """Horizontal bar chart of reasons with % labels; optional highlighted subset."""
    if df.empty:
        return empty_figure()
    d = df.iloc[::-1]
    if color_flag:
        colors = [flag_color if f else base_color for f in d[color_flag]]
    else:
        colors = [base_color or cfg.INK] * len(d)
    fig = go.Figure(go.Bar(
        y=d[label], x=d[value], orientation="h", marker_color=colors,
        text=[f"{c:,}  ·  {s:.1f}%" for c, s in zip(d[value], d["Share_Pct"])], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>%{x:,}<extra></extra>"))
    _base(fig, height=height, legend=False, margin=dict(l=10, r=100, t=20, b=10))
    fig.update_xaxes(title=dict(text="Number of rides"), range=[0, d[value].max() * 1.4])
    fig.update_yaxes(showgrid=False, automargin=True)
    if note:
        _note(fig, note, x=0.99, y=0.04, xanchor="right", yanchor="bottom")
    return fig


def customer_reasons_chart(reasons: pd.DataFrame) -> go.Figure:
    share = reasons.loc[reasons["Driver_Triggered"], "Share_Pct"].sum() if not reasons.empty else 0
    return reason_bars(reasons, color_flag="Driver_Triggered", flag_color=cfg.STATUS_COLORS["Canceled by Driver"],
                       base_color=cfg.STATUS_COLORS["Canceled by Customer"],
                       note=f"<span style='color:{cfg.STATUS_COLORS['Canceled by Driver']}'><b>Red</b></span> = triggered by the driver: {share:.1f}%")


def driver_reasons_chart(reasons: pd.DataFrame) -> go.Figure:
    share = reasons.loc[reasons["Owner"] == "Customer side", "Share_Pct"].sum() if not reasons.empty else 0
    r = reasons.assign(Customer_Side=reasons["Owner"] == "Customer side") if not reasons.empty else reasons
    return reason_bars(r, color_flag="Customer_Side" if not r.empty else None, flag_color=cfg.PAYMENT_COLORS["Debit Card"],
                       base_color=cfg.STATUS_COLORS["Canceled by Driver"],
                       note=f"<span style='color:{cfg.PAYMENT_COLORS['Debit Card']}'><b>Purple</b></span> = cites the customer side: {share:.1f}%")


def failure_attribution_chart(att: pd.DataFrame) -> go.Figure:
    """Root-cause split of all failed bookings (supply side vs customer-owned)."""
    if att.empty:
        return empty_figure()
    a = att.iloc[::-1]
    colors = [cfg.STATUS_COLORS["Canceled by Driver"] if s else cfg.STATUS_COLORS["Canceled by Customer"] for s in a["Supply_Side"]]
    fig = go.Figure(go.Bar(
        y=a["Root_Cause"], x=a["Failed_Bookings"], orientation="h", marker_color=colors,
        text=[f"{c:,}  ·  {s:.1f}%" for c, s in zip(a["Failed_Bookings"], a["Share_Pct"])], textposition="outside", cliponaxis=False,
        customdata=a["Quoted_Fare_Lost"], hovertemplate="%{y}<br>%{x:,} bookings<br>Quoted fare lost: ₹%{customdata:,.0f}<extra></extra>"))
    _base(fig, height=320, legend=False, margin=dict(l=10, r=110, t=20, b=10))
    fig.update_xaxes(title=dict(text="Failed bookings"), range=[0, a["Failed_Bookings"].max() * 1.4])
    fig.update_yaxes(showgrid=False)
    supply = att.loc[att["Supply_Side"], "Share_Pct"].sum()
    _note(fig, f"<b>{supply:.0f}%</b> of failures are driver-side (red)<br>Only {100 - supply:.0f}% are truly customer-owned", x=0.99, y=0.04, xanchor="right", yanchor="bottom")
    return fig


# =========================================================================== #
# Ratings & customers
# =========================================================================== #
def rating_hist(rd: pd.DataFrame, kind: str = "Driver") -> go.Figure:
    """Rides per 0.1-step rating (Power BI: Driver / Customer Ratings)."""
    if rd.empty or rd[kind].sum() == 0:
        return empty_figure()
    color = cfg.INK if kind == "Driver" else cfg.LIME
    mean = float((rd["Rating"] * rd[kind]).sum() / rd[kind].sum())
    fig = go.Figure(go.Bar(x=rd["Rating"], y=rd[kind], marker_color=color, marker_line=dict(color=cfg.INK, width=0.5),
                           hovertemplate="Rating %{x:.1f}<br>%{y:,} rides<extra></extra>", name=f"{kind} ratings"))
    _base(fig, height=320, legend=False)
    fig.update_xaxes(title=dict(text=f"{kind} rating"), dtick=0.5, range=[2.9, 5.1])
    fig.update_yaxes(title=dict(text="Completed rides"), rangemode="tozero")
    fig.add_vline(x=mean, line_dash="dot", line_color=cfg.STATUS_COLORS["Canceled by Driver"], line_width=2)
    _note(fig, f"Mean {mean:.2f}. Spread evenly from 3.0 to 5.0<br>Nobody is rated below 3.0 - a rating floor", x=0.01, y=0.30, yanchor="top")
    return fig


def rating_heatmap(h: pd.DataFrame) -> go.Figure:
    """Customer-vs-driver rating cross-tab (Power BI: Customer vs. Driver Ratings)."""
    if h.empty or h.values.sum() == 0:
        return empty_figure()
    pct = h / h.values.sum() * 100
    fig = go.Figure(go.Heatmap(
        z=pct.values, x=[f"C {c}" for c in h.columns], y=[f"D {r}" for r in h.index],
        colorscale=[[0, "#F4F6F1"], [1, cfg.INK]], zmin=0, zmax=max(pct.values.max() * 1.6, 1), showscale=False,
        text=[[f"{v:.1f}%<br>{int(n):,}" for v, n in zip(rv, rn)] for rv, rn in zip(pct.values, h.values)],
        texttemplate="%{text}", textfont=dict(size=12),
        hovertemplate="Driver %{y} / Customer %{x}<br>%{z:.1f}% of rides<extra></extra>"))
    _base(fig, height=340, legend=False)
    fig.update_xaxes(title=dict(text="Customer rating band"), side="bottom")
    fig.update_yaxes(title=dict(text="Driver rating band"), autorange="reversed", showgrid=False)
    return fig


def customer_frequency_chart(freq: pd.DataFrame) -> go.Figure:
    """How many customers booked 1, 2, 3 ... times."""
    if freq.empty:
        return empty_figure()
    fig = go.Figure(go.Bar(
        x=freq["Bookings_Per_Customer"].astype(str), y=freq["Customers"], marker_color=cfg.INK,
        text=[f"{c:,}<br>{s:.1f}%" for c, s in zip(freq["Customers"], freq["Share_Pct"])], textposition="outside", cliponaxis=False,
        hovertemplate="%{x} booking(s): %{y:,} customers<extra></extra>"))
    _base(fig, height=340, legend=False)
    fig.update_xaxes(title=dict(text="Bookings per customer in July"))
    fig.update_yaxes(title=dict(text="Customers"), range=[0, freq["Customers"].max() * 1.22])
    one = freq.loc[freq["Bookings_Per_Customer"] == 1, "Share_Pct"].sum()
    _note(fig, f"{one:.1f}% booked exactly once", x=0.99, y=0.99, xanchor="right")
    return fig


def anomaly_bars(score: pd.DataFrame) -> go.Figure:
    """Size of each anomaly review queue."""
    if score.empty:
        return empty_figure()
    s = score.sort_values("Flagged")
    fig = go.Figure(go.Bar(
        y=s["Rule"], x=s["Flagged"], orientation="h", marker_color=cfg.STATUS_COLORS["Canceled by Customer"],
        text=[f"{n:,} {u}" for n, u in zip(s["Flagged"], s["Unit"])], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>%{x:,}<extra></extra>"))
    _base(fig, height=340, legend=False, margin=dict(l=10, r=110, t=20, b=10))
    fig.update_xaxes(title=dict(text="Flagged records"), range=[0, s["Flagged"].max() * 1.35])
    fig.update_yaxes(showgrid=False)
    return fig


def quick_bar(df: pd.DataFrame, x: str, y: str) -> go.Figure:
    """Bar chart of any two result columns - used by the SQL playground's 'Chart it' option."""
    if df.empty:
        return empty_figure()
    d = df.head(40)
    fig = go.Figure(go.Bar(x=d[x].astype(str), y=d[y], marker_color=cfg.INK,
                           hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>"))
    _base(fig, height=340, legend=False)
    fig.update_xaxes(title=dict(text=x), tickangle=-30)
    fig.update_yaxes(title=dict(text=y), rangemode="tozero")
    return fig
