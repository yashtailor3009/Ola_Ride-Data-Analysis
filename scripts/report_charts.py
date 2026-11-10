"""
scripts/report_charts.py
========================
Static, print-quality charts (PNG) for the PDF report - built from the same
``ola.metrics`` tables as the Streamlit app, so every number is identical.

Style: white background, ink text, brand colours, one annotation per chart that
states the takeaway. Font: Carlito (metric-compatible with Calibri; has the rupee sign).

Run directly to (re)generate all charts into ``reports/charts``:
    python scripts/report_charts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
import numpy as np                                   # noqa: E402
import pandas as pd                                  # noqa: E402
from matplotlib import font_manager                  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ola import config as cfg                        # noqa: E402
from ola import metrics as m                         # noqa: E402
from ola.data import load_clean                      # noqa: E402

FONT_DIR = Path("/usr/share/fonts/truetype/crosextra")
for f in FONT_DIR.glob("Carlito-*.ttf"):
    font_manager.fontManager.addfont(str(f))
plt.rcParams.update({
    "font.family": "Carlito", "font.size": 10, "axes.edgecolor": cfg.GRID, "axes.labelcolor": cfg.INK,
    "xtick.color": cfg.INK, "ytick.color": cfg.INK, "text.color": cfg.INK, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": cfg.GRID, "grid.linewidth": 0.7,
    "axes.axisbelow": True, "figure.facecolor": "white", "savefig.facecolor": "white", "axes.titleweight": "bold",
})
OUT = ROOT / "reports" / "charts"
W = 6.9          # figure width in inches (fits the A4 text block)
DPI = 200
RED, AMBER, GREEN = cfg.STATUS_COLORS["Canceled by Driver"], cfg.STATUS_COLORS["Canceled by Customer"], cfg.STATUS_COLORS["Success"]


def _save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path


def _note(ax, text, loc="upper right", fs=8.5):
    """Boxed takeaway annotation inside the axes."""
    x, y, ha, va = {"upper right": (0.985, 0.97, "right", "top"), "upper left": (0.015, 0.97, "left", "top"),
                    "lower right": (0.985, 0.04, "right", "bottom"), "lower left": (0.015, 0.04, "left", "bottom")}[loc]
    ax.text(x, y, text, transform=ax.transAxes, ha=ha, va=va, fontsize=fs, linespacing=1.35,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=cfg.GRID, lw=0.8))


def _inr(v, d=2):
    return f"₹{v / 1e6:.{d}f}M" if abs(v) >= 1e6 else f"₹{v:,.0f}"


def _despine_x(ax):
    ax.grid(axis="x", visible=False)


# =========================================================================== #
def daily_volume(df):
    d = m.daily_volume(df)
    fig, ax = plt.subplots(figsize=(W, 2.9))
    x = pd.to_datetime(d["Date"])
    ax.bar(x, d["Completed"], color=GREEN, label="Completed", width=0.8)
    ax.bar(x, d["Failed"], bottom=d["Completed"], color=RED, alpha=0.85, label="Failed", width=0.8)
    ax.plot(x, d["Bookings_7d_Avg"], color=cfg.INK, lw=2, label="7-day average")
    ax.set_ylabel("Bookings per day"); ax.set_ylim(0, d["Bookings"].max() * 1.25)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b")); _despine_x(ax)
    pk, lo = d.loc[d["Bookings"].idxmax()], d.loc[d["Bookings"].idxmin()]
    ax.annotate(f"Peak {int(pk['Bookings']):,}", (pd.to_datetime(pk["Date"]), pk["Bookings"]), xytext=(-34, 26),
                textcoords="offset points", ha="center", fontsize=8, arrowprops=dict(arrowstyle="-", color=cfg.INK))
    ax.annotate(f"Low {int(lo['Bookings']):,}", (pd.to_datetime(lo["Date"]), lo["Bookings"]), xytext=(14, 42),
                textcoords="offset points", ha="center", fontsize=8, arrowprops=dict(arrowstyle="-", color=cfg.INK))
    ax.set_xlim(x.min() - pd.Timedelta(days=1), x.max() + pd.Timedelta(days=2))
    cv = d["Bookings"].std() / d["Bookings"].mean() * 100
    _note(ax, f"Average {d['Bookings'].mean():,.0f}/day, variation {cv:.1f}%\nNo growth or decay in the month", "lower left")
    ax.legend(ncol=3, loc="upper center", frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 1.12))
    return _save(fig, "daily_volume")


def status_donut(df):
    s = m.status_breakdown(df)
    fig, ax = plt.subplots(figsize=(3.3, 3.0))
    ax.pie(s["Bookings"], colors=[cfg.STATUS_COLORS[k] for k in s["Booking_Status"]], startangle=90, counterclock=False,
           wedgeprops=dict(width=0.38, edgecolor="white", linewidth=2),
           autopct=lambda p: f"{p:.1f}%", pctdistance=0.81, textprops=dict(color="white", fontsize=8.5, fontweight="bold"))
    ax.text(0, 0.06, f"{int(s['Bookings'].sum()):,}", ha="center", fontsize=15, fontweight="bold")
    ax.text(0, -0.14, "bookings", ha="center", fontsize=8.5, color=cfg.MUTED)
    ax.legend(s["Booking_Status"], loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=2, frameon=False, fontsize=8)
    ax.set_aspect("equal")
    return _save(fig, "status_donut")


def hourly_weekday(df):
    hr, wd = m.hourly_demand(df), m.weekday_demand(df)
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.9), gridspec_kw={"wspace": 0.28})
    a.bar(hr["Ride_Hour"], hr["Bookings"], color=cfg.INK, alpha=0.9)
    a.axhline(hr["Bookings"].mean(), color=cfg.LIME, lw=2, ls=":")
    a.set_xlabel("Hour of day"); a.set_ylabel("Bookings"); a.set_ylim(0, hr["Bookings"].max() * 1.35); a.set_xticks(range(0, 24, 3)); _despine_x(a)
    spread = max(hr["Bookings"].max() / hr["Bookings"].mean() - 1, 1 - hr["Bookings"].min() / hr["Bookings"].mean()) * 100
    _note(a, f"All hours within ±{spread:.1f}%\nof the {hr['Bookings'].mean():,.0f} average", "upper left", 8)
    names = [n[:3] for n in wd["Day_Name"]]
    b.bar(names, wd["Total_Bookings"], color="#C9D2CC", label="Total in July")
    b.set_ylabel("Total bookings"); b.set_ylim(0, wd["Total_Bookings"].max() * 1.45); _despine_x(b)
    b2 = b.twinx(); b2.plot(names, wd["Avg_Bookings_Per_Day"], color=cfg.INK, marker="D", ms=6, lw=1.2, ls=":", label="Per calendar day")
    b2.set_ylim(0, wd["Total_Bookings"].max() * 1.45 / 4); b2.set_ylabel("Per calendar day"); b2.grid(False); b2.spines["right"].set_visible(True)
    b2.spines["right"].set_color(cfg.GRID)
    _note(b, "Mon-Wed = 5 days in July,\nthe others = 4. Per-day average\n(diamonds) is flat.", "upper right", 8)
    return _save(fig, "hourly_weekday")


def failure_attribution(df):
    a = m.failure_attribution(df).iloc[::-1]
    fig, ax = plt.subplots(figsize=(W, 2.3))
    colors = [RED if s else AMBER for s in a["Supply_Side"]]
    bars = ax.barh(a["Root_Cause"], a["Failed_Bookings"], color=colors)
    for r, (c, sh) in zip(bars, zip(a["Failed_Bookings"], a["Share_Pct"])):
        ax.text(r.get_width() + 250, r.get_y() + r.get_height() / 2, f"{c:,}  ·  {sh:.1f}%", va="center", fontsize=9)
    ax.set_xlim(0, a["Failed_Bookings"].max() * 1.28); ax.set_xlabel("Failed bookings"); ax.grid(axis="y", visible=False)
    sup = a.loc[a["Supply_Side"], "Share_Pct"].sum()
    _note(ax, f"{sup:.0f}% of failures are driver-side (red)\nOnly {100 - sup:.0f}% are truly customer-owned", "lower right")
    return _save(fig, "failure_attribution")


def cancel_reasons(df):
    c, d = m.customer_cancel_reasons(df).iloc[::-1], m.driver_cancel_reasons(df).iloc[::-1]
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.9), gridspec_kw={"wspace": 1.0})
    a.barh(c["Reason"], c["Count"], color=[RED if t else AMBER for t in c["Driver_Triggered"]])
    for y, (n, s) in enumerate(zip(c["Count"], c["Share_Pct"])):
        a.text(n + 80, y, f"{s:.1f}%", va="center", fontsize=8.5)
    a.set_title("Customers cancel because…", fontsize=10, loc="left"); a.set_xlim(0, c["Count"].max() * 1.25); a.grid(axis="y", visible=False)
    a.tick_params(axis="y", labelsize=8)
    PUR = cfg.PAYMENT_COLORS["Debit Card"]
    b.barh(d["Reason"], d["Count"], color=[PUR if o == "Customer side" else RED for o in d["Owner"]])
    for y, (n, s) in enumerate(zip(d["Count"], d["Share_Pct"])):
        b.text(n + 100, y, f"{s:.1f}%", va="center", fontsize=8.5)
    b.set_title("Drivers cancel because…", fontsize=10, loc="left"); b.set_xlim(0, d["Count"].max() * 1.25); b.grid(axis="y", visible=False)
    b.tick_params(axis="y", labelsize=8)
    dr = c.loc[c["Driver_Triggered"], "Share_Pct"].sum(); cu = d.loc[d["Owner"] == "Customer side", "Share_Pct"].sum()
    a.set_xlabel(f"Red = driver-triggered: {dr:.1f}%", fontsize=8.5, color=RED, fontweight="bold")
    b.set_xlabel(f"Purple = cites the rider: {cu:.1f}%", fontsize=8.5, color=PUR, fontweight="bold")
    return _save(fig, "cancel_reasons")


def revenue_waterfall(df):
    k, leak = m.kpis(df), m.revenue_leakage(df).set_index("Failure_Type")
    order = ["Driver cancellation", "Customer cancellation", "No driver found"]
    labels = ["Quoted value\nof all bookings", "Lost to driver\ncancellations", "Lost to customer\ncancellations", "Lost to no\ndriver found", "Realised\nrevenue"]
    fig, ax = plt.subplots(figsize=(W, 3.0))
    run = k["potential_value"]
    ax.bar(0, run, color=cfg.INK); ax.text(0, run + 8e5, _inr(run), ha="center", fontsize=9, fontweight="bold")
    for i, o in enumerate(order, start=1):
        d = leak.loc[o, "Quoted_Fare_Lost"]; run -= d
        ax.bar(i, d, bottom=run, color=RED); ax.text(i, run + d + 8e5, f"-{_inr(d)}", ha="center", fontsize=9, fontweight="bold")
    ax.bar(4, k["revenue"], color=GREEN); ax.text(4, k["revenue"] + 8e5, _inr(k["revenue"]), ha="center", fontsize=9, fontweight="bold")
    ax.set_xticks(range(5)); ax.set_xticklabels(labels, fontsize=8.5); ax.set_ylabel("Booking value (₹)"); ax.set_ylim(0, k["potential_value"] * 1.18)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1e6:.0f}M")); _despine_x(ax)
    _note(ax, f"{k['quoted_fare_lost'] / k['potential_value'] * 100:.1f}% of quoted value never converts\nRecover 10% = +{_inr(k['quoted_fare_lost'] * 0.1)} (+{0.1 * k['quoted_fare_lost'] / k['revenue'] * 100:.1f}% revenue)", "upper right")
    return _save(fig, "revenue_waterfall")


def payments_vehicles(df):
    pay, veh = m.payment_summary(df), m.vehicle_summary(df)
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.9), gridspec_kw={"wspace": 0.3})
    a.bar([p.replace(" ", "\n") for p in pay["Payment_Method"]], pay["Revenue"], color=[cfg.PAYMENT_COLORS[p] for p in pay["Payment_Method"]])
    for i, (r, s) in enumerate(zip(pay["Revenue"], pay["Revenue_Share_Pct"])):
        a.text(i, r + 3e5, f"{_inr(r)}\n{s:.1f}%", ha="center", fontsize=8.5)
    a.set_ylim(0, pay["Revenue"].max() * 1.3); a.set_ylabel("Revenue (₹)"); _despine_x(a)
    a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1e6:.0f}M"))
    a.set_title("Revenue by payment method", fontsize=10, loc="left")
    v = veh.sort_values("Fare_Per_Km", ascending=False)
    b.bar(v["Vehicle_Type"], v["Fare_Per_Km"], color=[cfg.VEHICLE_COLORS[t] for t in v["Vehicle_Type"]])
    for i, x in enumerate(v["Fare_Per_Km"]):
        b.text(i, x + 1, f"₹{x:.0f}", ha="center", fontsize=8.5)
    b.set_ylim(0, v["Fare_Per_Km"].max() * 1.25); b.set_ylabel("Revenue per km (₹)"); _despine_x(b); b.tick_params(axis="x", labelsize=7.5, rotation=30)
    b.set_title("Revenue per km driven", fontsize=10, loc="left")
    _note(b, "Auto: same fare,\n~10 km vs ~25 km trips", "upper right", 8)
    return _save(fig, "payments_vehicles")


def pricing(df):
    done = df[df["Is_Successful"] == 1]
    corr = done["Booking_Value"].corr(done["Ride_Distance"])
    bands = m.distance_band_summary(df)
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 3.0), gridspec_kw={"wspace": 0.32})
    s = done.sample(4000, random_state=7)
    a.scatter(s["Ride_Distance"], s["Booking_Value"], s=6, alpha=0.25, color=cfg.INK)
    a.set_xlabel("Ride distance (km)"); a.set_ylabel("Fare (₹)"); a.set_ylim(0, 3200)
    _note(a, f"Correlation = {corr:.3f}\n3 km can cost as much as 45 km", "upper right", 8.5)
    a.set_title("Fare vs distance (4,000 rides)", fontsize=10, loc="left")
    b.bar(bands["Distance_Band"], bands["Avg_Fare"], color=cfg.INK, alpha=0.9)
    b.set_ylim(0, bands["Avg_Fare"].max() * 1.6); b.set_ylabel("Average fare (₹)"); b.tick_params(axis="x", labelsize=7.5, rotation=30); _despine_x(b)
    b2 = b.twinx(); b2.plot(bands["Distance_Band"], bands["Fare_Per_Km"], color=RED, marker="o", lw=2)
    for i, x in enumerate(bands["Fare_Per_Km"]):
        b2.text(i, x + 10, f"₹{x:.0f}/km", ha="center", fontsize=7.5, color=RED, bbox=dict(fc="white", ec="none", pad=0.6))
    b2.set_ylim(0, bands["Fare_Per_Km"].max() * 1.25); b2.grid(False); b2.set_ylabel("Fare per km (₹)", color=RED)
    b2.spines["right"].set_visible(True); b2.spines["right"].set_color(cfg.GRID)
    b.set_title("Avg fare is flat; price per km collapses", fontsize=10, loc="left")
    return _save(fig, "pricing")


def vehicles(df):
    veh, vr = m.vehicle_summary(df), m.vehicle_ratings(df)
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.9), gridspec_kw={"wspace": 0.55})
    t = veh.sort_values("Total_Distance_Km", ascending=False).head(5).iloc[::-1]
    a.barh(t["Vehicle_Type"], t["Total_Distance_Km"], color=[cfg.VEHICLE_COLORS[v] for v in t["Vehicle_Type"]])
    for y, (d, avg) in enumerate(zip(t["Total_Distance_Km"], t["Avg_Distance_Km"])):
        a.text(d + 3000, y, f"{d / 1000:,.0f}K km", va="center", fontsize=8.5)
    a.set_xlim(0, t["Total_Distance_Km"].max() * 1.3); a.set_title("Top 5 vehicle types by ride distance", fontsize=10, loc="left"); a.grid(axis="y", visible=False)
    a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}K"))
    b.bar(vr["Vehicle_Type"], vr["Avg_Customer_Rating"], color=[cfg.VEHICLE_COLORS[v] for v in vr["Vehicle_Type"]])
    for i, x in enumerate(vr["Avg_Customer_Rating"]):
        b.text(i, x + 0.07, f"{x:.2f}", ha="center", fontsize=8.5)
    b.set_ylim(0, 5.4); b.set_ylabel("Avg customer rating"); b.tick_params(axis="x", labelsize=7.5, rotation=30); _despine_x(b)
    b.set_title("Average customer rating", fontsize=10, loc="left")
    _note(b, f"Spread {vr['Avg_Customer_Rating'].max() - vr['Avg_Customer_Rating'].min():.2f} pts:\nnot significant", "upper right", 8)
    return _save(fig, "vehicles")


def customers(df):
    freq, c = m.customer_frequency(df), m.customer_outcomes(df)
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.7), gridspec_kw={"wspace": 0.35, "width_ratios": [1.5, 1]})
    a.bar(freq["Bookings_Per_Customer"].astype(str), freq["Customers"], color=cfg.INK)
    for i, (n, s) in enumerate(zip(freq["Customers"], freq["Share_Pct"])):
        a.text(i, n + 1500, f"{n:,}\n{('<0.1' if s < 0.05 else f'{s:.1f}')}%", ha="center", fontsize=8)
    a.set_ylim(0, freq["Customers"].max() * 1.25); a.set_xlabel("Bookings per customer in July"); a.set_ylabel("Customers"); _despine_x(a)
    a.set_title("Almost everyone books once", fontsize=10, loc="left")
    got = c["customers"] - c["never_completed"]
    b.pie([got, c["never_completed"]], colors=[GREEN, RED], startangle=90, counterclock=False, wedgeprops=dict(width=0.30, edgecolor="white", linewidth=2))
    b.text(0, 0.08, f"{c['never_completed_rate']:.1f}%", ha="center", fontsize=14, fontweight="bold"); b.text(0, -0.22, "no completed ride", ha="center", fontsize=7.5, color=cfg.MUTED)
    b.set_aspect("equal"); b.set_title("Customers who never got a ride", fontsize=10, loc="left")
    return _save(fig, "customers")


def ratings(df):
    rd, h = m.rating_distribution(df), m.rating_heatmap(df)
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.9), gridspec_kw={"wspace": 0.32, "width_ratios": [1.2, 1]})
    a.bar(rd["Rating"] - 0.02, rd["Driver"], width=0.04, color=cfg.INK, label="Driver")
    a.bar(rd["Rating"] + 0.02, rd["Customer"], width=0.04, color=cfg.LIME, label="Customer", edgecolor=cfg.INK, linewidth=0.3)
    a.set_xlabel("Rating"); a.set_ylabel("Completed rides"); a.legend(frameon=False, fontsize=8, loc="upper left", ncol=1); _despine_x(a)
    a.set_xlim(2.9, 5.1); a.set_ylim(0, rd[["Driver", "Customer"]].values.max() * 1.45)
    _note(a, "Flat from 3.0 to 5.0;\nnobody is rated below 3.0", "upper right", 8)
    pct = h / h.values.sum() * 100
    im = b.imshow(pct.values, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("g", ["#FFFFFF", "#B9D86A"]), vmin=0, vmax=pct.values.max() * 1.05)
    for i in range(4):
        for j in range(4):
            b.text(j, i, f"{pct.values[i, j]:.1f}%", ha="center", va="center", fontsize=8, color=cfg.INK)
    b.set_xticks(range(4)); b.set_xticklabels(h.columns, fontsize=7.5); b.set_yticks(range(4)); b.set_yticklabels(h.index, fontsize=7.5)
    b.set_xlabel("Customer rating band"); b.set_ylabel("Driver rating band"); b.grid(False)
    for sp in b.spines.values(): sp.set_visible(False)
    b.set_title("No diagonal = independent", fontsize=10, loc="left")
    return _save(fig, "ratings")


def anomalies(df):
    s = m.anomaly_scorecard(df).sort_values("Flagged")
    fig, ax = plt.subplots(figsize=(W, 2.3))
    bars = ax.barh(s["Rule"], s["Flagged"], color=AMBER)
    for r, (n, u) in zip(bars, zip(s["Flagged"], s["Unit"])):
        ax.text(r.get_width() + 60, r.get_y() + r.get_height() / 2, f"{n:,} {u}", va="center", fontsize=8.5)
    ax.set_xlim(0, s["Flagged"].max() * 1.22); ax.grid(axis="y", visible=False); ax.set_xlabel("Flagged records"); ax.tick_params(axis="y", labelsize=8.5)
    return _save(fig, "anomalies")


def incomplete(df):
    inc = m.incomplete_reasons(df).iloc[::-1]
    fig, ax = plt.subplots(figsize=(3.3, 2.1))
    ax.barh(inc["Reason"], inc["Count"], color=AMBER)
    for y, (n, s) in enumerate(zip(inc["Count"], inc["Share_Pct"])):
        ax.text(n + 30, y, f"{n:,} · {s:.1f}%", va="center", fontsize=8.5)
    ax.set_xlim(0, inc["Count"].max() * 1.5); ax.grid(axis="y", visible=False); ax.set_xlabel("Incomplete rides")
    return _save(fig, "incomplete")


def build_all(df: pd.DataFrame | None = None) -> dict[str, Path]:
    df = load_clean() if df is None else df
    funcs = [daily_volume, status_donut, hourly_weekday, failure_attribution, cancel_reasons, revenue_waterfall,
             payments_vehicles, pricing, vehicles, customers, ratings, anomalies, incomplete]
    return {f.__name__: f(df) for f in funcs}


if __name__ == "__main__":
    out = build_all()
    print("charts:", ", ".join(p.name for p in out.values()))
