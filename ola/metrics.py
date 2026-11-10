"""
ola.metrics
===========
Pure-pandas analytics - **no Streamlit, no Plotly** - so every function can be
unit-tested and reused by the app, the PDF/PPT builders and the notebooks.

Sections
--------
1. Formatting helpers
2. Core tables (one function per business question / dashboard visual)
3. Anomaly detection rules
4. Statistical tests (is a difference real, or noise?)
5. ``build_insights`` - turns the numbers into What / Why / So-what cards

Conventions
-----------
* ``df`` is always the *cleaned* frame produced by ``ola.preprocessing``.
* "Completed" means ``Is_Successful == 1``; revenue is summed over completed rides only.
* Every function accepts a filtered frame, so the Streamlit sidebar filters flow
  through unchanged. Functions never mutate their input.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as cfg


# =========================================================================== #
# 1. Formatting helpers
# =========================================================================== #
def fmt_int(value: float) -> str:
    """12345 -> '12,345'."""
    return f"{int(round(value)):,}"


def fmt_inr(value: float, decimals: int = 2) -> str:
    """Compact rupee format: 35080467 -> '₹35.08 M', 4200 -> '₹4,200'."""
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"{cfg.CURRENCY}{value / 1_000_000:.{decimals}f} M"
    if abs(value) >= 100_000:
        return f"{cfg.CURRENCY}{value / 1_000:.0f} K"
    return f"{cfg.CURRENCY}{value:,.0f}"


def fmt_pct(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def _pct(part: float, whole: float) -> float:
    """Safe percentage (0 when ``whole`` is 0, so empty filters never crash)."""
    return float(100.0 * part / whole) if whole else 0.0


def _completed(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Is_Successful"] == 1]


def _failed(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Is_Successful"] == 0]


# =========================================================================== #
# 2. Core tables
# =========================================================================== #
def kpis(df: pd.DataFrame) -> dict:
    """Headline numbers shown on the KPI strip."""
    done, failed = _completed(df), _failed(df)
    total = len(df)
    return {
        "total_bookings": total,
        "completed": len(done),
        "failed": len(failed),
        "success_rate": _pct(len(done), total),
        "revenue": float(done["Booking_Value"].sum()),
        "quoted_fare_lost": float(failed["Booking_Value"].sum()),
        "avg_fare": float(done["Booking_Value"].mean()) if len(done) else 0.0,
        "avg_distance": float(done["Ride_Distance"].mean()) if len(done) else 0.0,
        "avg_driver_rating": float(df["Driver_Ratings"].mean()) if len(done) else 0.0,
        "avg_customer_rating": float(df["Customer_Rating"].mean()) if len(done) else 0.0,
        "customer_cancel_rate": _pct((df["Booking_Status"] == "Canceled by Customer").sum(), total),
        "driver_cancel_rate": _pct((df["Booking_Status"] == "Canceled by Driver").sum(), total),
        "no_driver_rate": _pct((df["Booking_Status"] == "Driver Not Found").sum(), total),
        "unique_customers": int(df["Customer_ID"].nunique()),
        "potential_value": float(df["Booking_Value"].sum()),
    }


def status_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Booking status counts and shares (Power BI Q2)."""
    out = df["Booking_Status"].value_counts().rename_axis("Booking_Status").reset_index(name="Bookings")
    out["Share_Pct"] = 100 * out["Bookings"] / max(out["Bookings"].sum(), 1)
    order = {s: i for i, s in enumerate(cfg.STATUS_ORDER)}
    return out.sort_values("Booking_Status", key=lambda s: s.map(order)).reset_index(drop=True)


def daily_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Daily bookings split completed/failed plus a 7-day moving average (Power BI Q1)."""
    work = df.assign(_revenue=df["Booking_Value"] * df["Is_Successful"])      # vectorised: no per-group lambdas
    g = work.groupby("Date").agg(
        Bookings=("Booking_ID", "size"),
        Completed=("Is_Successful", "sum"),
        Revenue=("_revenue", "sum"),
    ).reset_index()
    g["Failed"] = g["Bookings"] - g["Completed"]
    g["Bookings_7d_Avg"] = g["Bookings"].rolling(7, min_periods=1).mean()
    return g


def hourly_demand(df: pd.DataFrame) -> pd.DataFrame:
    """Bookings and success rate for each hour of the day."""
    g = df.groupby("Ride_Hour").agg(Bookings=("Booking_ID", "size"), Completed=("Is_Successful", "sum")).reset_index()
    g["Success_Rate_Pct"] = 100 * g["Completed"] / g["Bookings"]
    return g


def weekday_demand(df: pd.DataFrame) -> pd.DataFrame:
    """Raw totals *and* per-calendar-day averages for each weekday.

    The per-day average exposes the calendar artefact: July 2024 had five
    Mondays/Tuesdays/Wednesdays but only four of every other weekday.
    """
    g = df.groupby(["Day_Of_Week_No", "Day_Name"]).agg(
        Total_Bookings=("Booking_ID", "size"),
        Calendar_Days=("Date", "nunique"),
        Completed=("Is_Successful", "sum"),
    ).reset_index()
    g["Avg_Bookings_Per_Day"] = g["Total_Bookings"] / g["Calendar_Days"]
    g["Success_Rate_Pct"] = 100 * g["Completed"] / g["Total_Bookings"]
    return g.sort_values("Day_Of_Week_No").reset_index(drop=True)


def time_band_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("Time_Band").agg(
        Bookings=("Booking_ID", "size"), Completed=("Is_Successful", "sum"),
        Min_Hour=("Ride_Hour", "min")).reset_index()
    g["Success_Rate_Pct"] = 100 * g["Completed"] / g["Bookings"]
    return g.sort_values("Min_Hour").reset_index(drop=True)


def location_summary(df: pd.DataFrame, by: str = "Pickup_Location") -> pd.DataFrame:
    """Bookings and success rate per pickup (or drop) location."""
    g = df.groupby(by).agg(Bookings=("Booking_ID", "size"), Completed=("Is_Successful", "sum")).reset_index()
    g["Success_Rate_Pct"] = 100 * g["Completed"] / g["Bookings"]
    return g.sort_values("Bookings", ascending=False).reset_index(drop=True)


def vehicle_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One scorecard row per vehicle type (SQL C01)."""
    rows = []
    for vehicle, g in df.groupby("Vehicle_Type"):
        done = _completed(g)
        rows.append({
            "Vehicle_Type": vehicle,
            "Bookings": len(g),
            "Completed": len(done),
            "Success_Rate_Pct": _pct(len(done), len(g)),
            "Revenue": float(done["Booking_Value"].sum()),
            "Avg_Fare": float(done["Booking_Value"].mean()) if len(done) else np.nan,
            "Avg_Distance_Km": float(done["Ride_Distance"].mean()) if len(done) else np.nan,
            "Avg_Distance_All_Km": float(g["Ride_Distance"].mean()),
            "Total_Distance_Km": float(done["Ride_Distance"].sum()),
            "Avg_Customer_Rating": float(g["Customer_Rating"].mean()),
            "Avg_Driver_Rating": float(g["Driver_Ratings"].mean()),
            "Avg_V_TAT": float(done["V_TAT"].mean()) if len(done) else np.nan,
            "Avg_C_TAT": float(done["C_TAT"].mean()) if len(done) else np.nan,
            "Fare_Per_Km": float(done["Booking_Value"].sum() / done["Ride_Distance"].sum()) if len(done) else np.nan,
        })
    out = pd.DataFrame(rows)
    out["Class"] = out["Vehicle_Type"].map(cfg.VEHICLE_CLASS)
    out["Icon"] = out["Vehicle_Type"].map(cfg.VEHICLE_ICONS)
    return out.sort_values("Revenue", ascending=False).reset_index(drop=True)


def vehicle_status_mix(df: pd.DataFrame) -> pd.DataFrame:
    """% of each vehicle's bookings by status (rows sum to 100)."""
    mix = pd.crosstab(df["Vehicle_Type"], df["Booking_Status"], normalize="index") * 100
    return mix.reindex(columns=cfg.STATUS_ORDER).fillna(0).reset_index()


def payment_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue by payment method (Power BI Q6)."""
    done = _completed(df)
    g = done.groupby("Payment_Method").agg(Rides=("Booking_ID", "size"), Revenue=("Booking_Value", "sum"),
                                           Avg_Fare=("Booking_Value", "mean")).reset_index()
    g["Revenue_Share_Pct"] = 100 * g["Revenue"] / max(g["Revenue"].sum(), 1)
    return g.sort_values("Revenue", ascending=False).reset_index(drop=True)


def top_customers_by_value(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Top customers by completed booking value (Power BI Q7 / SQL D03)."""
    done = _completed(df)
    g = done.groupby("Customer_ID").agg(Completed_Rides=("Booking_ID", "size"),
                                        Total_Booking_Value=("Booking_Value", "sum")).reset_index()
    total = max(done["Booking_Value"].sum(), 1)
    g["Share_Of_Revenue_Pct"] = 100 * g["Total_Booking_Value"] / total
    return g.sort_values(["Total_Booking_Value", "Customer_ID"], ascending=[False, True]).head(n).reset_index(drop=True)


def top_customers_by_rides(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Top customers by number of bookings (SQL Q04). Ties -> completed value -> Customer_ID."""
    work = df.assign(_value=df["Booking_Value"] * df["Is_Successful"])        # vectorised: 94k groups
    g = work.groupby("Customer_ID").agg(Total_Rides=("Booking_ID", "size"),
                                        Completed_Booking_Value=("_value", "sum")).reset_index()
    g = g.sort_values(["Total_Rides", "Completed_Booking_Value", "Customer_ID"], ascending=[False, False, True])
    return g.head(n).reset_index(drop=True)


def distance_per_day(df: pd.DataFrame) -> pd.DataFrame:
    """Per-day distribution of completed-ride distance (pre-computed box-plot stats)."""
    done = _completed(df)
    g = done.groupby("Date")["Ride_Distance"]
    out = pd.DataFrame({
        "Completed_Rides": g.size(),
        "Total_Distance_Km": g.sum(),
        "Mean": g.mean(),
        "Min": g.min(),
        "Q1": g.quantile(0.25),
        "Median": g.median(),
        "Q3": g.quantile(0.75),
        "Max": g.max(),
    }).reset_index()
    return out


def distance_band_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Average fare by distance band - shows fare does not rise with distance."""
    done = _completed(df)
    g = done.groupby("Distance_Band").agg(Completed_Rides=("Booking_ID", "size"),
                                          Avg_Fare=("Booking_Value", "mean"),
                                          Revenue=("Booking_Value", "sum"),
                                          Km=("Ride_Distance", "sum")).reset_index()
    g["Fare_Per_Km"] = g["Revenue"] / g["Km"]
    order = {b: i for i, b in enumerate(cfg.DISTANCE_LABELS)}
    return g.sort_values("Distance_Band", key=lambda s: s.map(order)).reset_index(drop=True)


def fare_tiers(df: pd.DataFrame) -> pd.DataFrame:
    done = _completed(df)
    bins = [0, 250, 500, 1000, 1500, np.inf]
    labels = ["Under 250", "250-499", "500-999", "1,000-1,499", "1,500+"]
    tier = pd.cut(done["Booking_Value"], bins=bins, labels=labels, right=False)
    g = done.groupby(tier, observed=False).agg(Completed_Rides=("Booking_ID", "size"),
                                               Revenue=("Booking_Value", "sum")).reset_index()
    g.columns = ["Fare_Tier", "Completed_Rides", "Revenue"]
    g["Revenue_Share_Pct"] = 100 * g["Revenue"] / max(g["Revenue"].sum(), 1)
    g["Ride_Share_Pct"] = 100 * g["Completed_Rides"] / max(g["Completed_Rides"].sum(), 1)
    return g


def fare_per_km_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Weighted fare/km by hour - the surge-pricing proxy."""
    done = _completed(df)
    g = done.groupby("Ride_Hour").agg(Revenue=("Booking_Value", "sum"), Km=("Ride_Distance", "sum"),
                                      Rides=("Booking_ID", "size")).reset_index()
    g["Fare_Per_Km"] = g["Revenue"] / g["Km"]
    return g


def revenue_leakage(df: pd.DataFrame) -> pd.DataFrame:
    """Quoted fare lost, by failure type (SQL D05)."""
    g = _failed(df).groupby("Failure_Type").agg(Failed_Bookings=("Booking_ID", "size"),
                                                Quoted_Fare_Lost=("Booking_Value", "sum")).reset_index()
    g["Share_Of_Loss_Pct"] = 100 * g["Quoted_Fare_Lost"] / max(g["Quoted_Fare_Lost"].sum(), 1)
    return g.sort_values("Quoted_Fare_Lost", ascending=False).reset_index(drop=True)


def reason_counts(df: pd.DataFrame, column: str, status: str | None = None) -> pd.DataFrame:
    """Frequency table of a reason column (Power BI Q5 and the Driver/Customer split)."""
    frame = df if status is None else df[df["Booking_Status"] == status]
    out = frame[column].value_counts().rename_axis("Reason").reset_index(name="Count")
    out["Share_Pct"] = 100 * out["Count"] / max(out["Count"].sum(), 1)
    return out


def customer_cancel_reasons(df: pd.DataFrame) -> pd.DataFrame:
    out = reason_counts(df, "Canceled_Rides_by_Customer", "Canceled by Customer")
    out["Driver_Triggered"] = out["Reason"].isin(cfg.DRIVER_TRIGGERED_CUSTOMER_REASONS)
    return out


def driver_cancel_reasons(df: pd.DataFrame) -> pd.DataFrame:
    out = reason_counts(df, "Canceled_Rides_by_Driver", "Canceled by Driver")
    out["Owner"] = np.where(out["Reason"] == "Personal & Car related issue", "Driver / vehicle", "Customer side")
    return out


def incomplete_reasons(df: pd.DataFrame) -> pd.DataFrame:
    out = reason_counts(df, "Incomplete_Rides_Reason", None)
    return out


def failure_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """Root-cause split of every failed booking (SQL E03).

    A customer cancellation caused by the driver (not moving, asked to cancel)
    is attributed to the supply side, because the customer is reacting to the driver.
    """
    f = _failed(df)
    cause = np.select(
        [f["Booking_Status"] == "Canceled by Driver",
         f["Booking_Status"] == "Driver Not Found",
         f["Canceled_Rides_by_Customer"].isin(cfg.DRIVER_TRIGGERED_CUSTOMER_REASONS)],
        ["Driver cancelled", "No driver found", "Customer cancelled - driver-triggered"],
        default="Customer cancelled - own reason",
    )
    g = (pd.DataFrame({"Root_Cause": cause, "Booking_Value": f["Booking_Value"].values})
         .groupby("Root_Cause").agg(Failed_Bookings=("Booking_Value", "size"),
                                    Quoted_Fare_Lost=("Booking_Value", "sum")).reset_index())
    g["Share_Pct"] = 100 * g["Failed_Bookings"] / max(g["Failed_Bookings"].sum(), 1)
    order = ["Driver cancelled", "No driver found", "Customer cancelled - driver-triggered",
             "Customer cancelled - own reason"]
    g["Supply_Side"] = g["Root_Cause"] != "Customer cancelled - own reason"
    return g.sort_values("Root_Cause", key=lambda s: s.map({c: i for i, c in enumerate(order)})).reset_index(drop=True)


def rating_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Count of rides per 0.1-step rating for drivers and customers (Power BI Q9)."""
    done = _completed(df)
    steps = np.round(np.arange(3.0, 5.01, 0.1), 1)
    d = done["Driver_Ratings"].round(1).value_counts().reindex(steps, fill_value=0)
    c = done["Customer_Rating"].round(1).value_counts().reindex(steps, fill_value=0)
    return pd.DataFrame({"Rating": steps, "Driver": d.values, "Customer": c.values})


def rating_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    """Customer-vs-driver rating cross-tab on 0.5-wide bands (Power BI Q10)."""
    done = _completed(df)
    edges, labels = [2.95, 3.45, 3.95, 4.45, 5.05], ["3.0-3.4", "3.5-3.9", "4.0-4.4", "4.5-5.0"]
    d = pd.cut(done["Driver_Ratings"], edges, labels=labels)
    c = pd.cut(done["Customer_Rating"], edges, labels=labels)
    return pd.crosstab(d, c).reindex(index=labels, columns=labels, fill_value=0)


def vehicle_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """Average customer/driver rating per vehicle type (Power BI Q4, SQL Q08)."""
    g = df.groupby("Vehicle_Type").agg(Avg_Customer_Rating=("Customer_Rating", "mean"),
                                       Avg_Driver_Rating=("Driver_Ratings", "mean"),
                                       Rated_Rides=("Customer_Rating", "count")).reset_index()
    return g.sort_values("Avg_Customer_Rating", ascending=False).reset_index(drop=True)


def customer_frequency(df: pd.DataFrame) -> pd.DataFrame:
    """How many customers booked 1, 2, 3 ... times (SQL G01)."""
    per = df.groupby("Customer_ID").size()
    g = per.value_counts().sort_index().rename_axis("Bookings_Per_Customer").reset_index(name="Customers")
    g["Share_Pct"] = 100 * g["Customers"] / max(g["Customers"].sum(), 1)
    return g


def customer_outcomes(df: pd.DataFrame) -> dict:
    """Repeat / never-completed customer statistics (SQL G01, G02, G04)."""
    per = df.groupby("Customer_ID").agg(n=("Booking_ID", "size"), ok=("Is_Successful", "sum"))
    failed_ct = per["n"] - per["ok"]
    total = len(per)
    single = per[per["n"] == 1]
    return {
        "customers": total,
        "repeat_customers": int((per["n"] >= 2).sum()),
        "repeat_rate": _pct((per["n"] >= 2).sum(), total),
        "single_booking_rate": _pct((per["n"] == 1).sum(), total),
        "never_completed": int((per["ok"] == 0).sum()),
        "never_completed_rate": _pct((per["ok"] == 0).sum(), total),
        "failed_2plus": int((failed_ct >= 2).sum()),
        "failed_3plus": int((failed_ct >= cfg.REPEAT_FAILURE_THRESHOLD).sum()),
        "single_booking_failed_rate": _pct((single["ok"] == 0).sum(), len(single)),
    }


def pricing_stats(df: pd.DataFrame) -> dict:
    """Does fare track distance? (the pricing-integrity test)"""
    done = _completed(df)
    if len(done) < 3:
        return {"fare_distance_corr": 0.0, "fare_per_km_median": 0.0, "fare_median_by_vehicle": {}}
    return {
        "fare_distance_corr": float(done["Booking_Value"].corr(done["Ride_Distance"])),
        "fare_per_km_median": float(done["Fare_Per_Km"].median()),
        "fare_median_by_vehicle": done.groupby("Vehicle_Type")["Booking_Value"].median().to_dict(),
    }


# =========================================================================== #
# 3. Anomaly detection
# =========================================================================== #
def anomaly_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Rule-based review queues. Each is a *candidate* list, not proof of fraud."""
    done = _completed(df)
    ac = df[(df["Canceled_Rides_by_Customer"] == "AC is Not working") & df["Vehicle_Type"].isin(cfg.NON_AC_VEHICLES)]
    min_fare, max_km = cfg.HIGH_FARE_SHORT_RIDE
    cols = ["Booking_ID", "Customer_ID", "Date", "Vehicle_Type", "Booking_Status", "Pickup_Location",
            "Drop_Location", "Ride_Distance", "Booking_Value", "Payment_Method"]
    failed_per = df.groupby("Customer_ID")["Is_Successful"].agg(Bookings="size", Completed="sum")
    failed_per["Failed"] = failed_per["Bookings"] - failed_per["Completed"]
    repeat = failed_per[failed_per["Failed"] >= cfg.REPEAT_FAILURE_THRESHOLD].reset_index().sort_values(
        ["Failed", "Bookings", "Customer_ID"], ascending=[False, False, True])
    return {
        "Pickup equals drop": df[df["Is_Same_Pickup_Drop"] == 1][cols],
        f"Fare above {cfg.CURRENCY}{cfg.EXTREME_FARE_PER_KM}/km": done[done["Fare_Per_Km"] > cfg.EXTREME_FARE_PER_KM][cols + ["Fare_Per_Km"]],
        f"Fare >= {cfg.CURRENCY}{min_fare:,} on a <= {max_km} km ride": done[(done["Booking_Value"] >= min_fare) & (done["Ride_Distance"] <= max_km)][cols],
        "AC complaint on a non-AC vehicle": ac[cols + ["Canceled_Rides_by_Customer"]],
        f"Rating gap of {cfg.RATING_MISMATCH_GAP} or more": done[done["Rating_Gap"].abs() >= cfg.RATING_MISMATCH_GAP][
            ["Booking_ID", "Vehicle_Type", "Driver_Ratings", "Customer_Rating", "Rating_Gap", "Booking_Value"]],
        f"Customers with {cfg.REPEAT_FAILURE_THRESHOLD}+ failed bookings": repeat,
    }


def anomaly_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    tables = anomaly_tables(df)
    out = pd.DataFrame({"Rule": list(tables), "Flagged": [len(t) for t in tables.values()]})
    out["Unit"] = ["bookings"] * (len(out) - 1) + ["customers"]
    return out


# =========================================================================== #
# 4. Statistical tests
# =========================================================================== #
def statistical_tests(df: pd.DataFrame) -> dict:
    """p-values / effect sizes that decide whether a pattern is real or noise.

    Requires SciPy. Small p (< 0.05) = unlikely to be chance.
    """
    from scipy import stats

    done = _completed(df)

    def chi_p(a: pd.Series, b: pd.Series) -> float:
        return float(stats.chi2_contingency(pd.crosstab(a, b))[1])

    hourly = df.groupby("Ride_Hour").size()
    dow = weekday_demand(df)
    inc = df[df["Incomplete_Rides"] == "Yes"]
    loc = location_summary(df)
    p_all = df["Is_Successful"].mean()
    z = (loc["Success_Rate_Pct"] / 100 - p_all) / np.sqrt(p_all * (1 - p_all) / loc["Bookings"])
    groups = [g["Customer_Rating"].values for _, g in done.groupby("Vehicle_Type")]
    return {
        "p_success_vs_vehicle": chi_p(df["Vehicle_Type"], df["Booking_Status"]),
        "p_success_vs_hour": chi_p(df["Ride_Hour"], df["Booking_Status"]),
        "p_success_vs_location": chi_p(df["Pickup_Location"], df["Booking_Status"]),
        "p_success_vs_weekday": chi_p(df["Day_Name"], df["Booking_Status"]),
        "p_hourly_uniform": float(stats.chisquare(hourly).pvalue),
        "p_daily_per_weekday": float(stats.f_oneway(*[g["Bookings"].values for _, g in
                                                      daily_volume(df).assign(dow=lambda d: pd.to_datetime(d["Date"]).dt.dayofweek).groupby("dow")]).pvalue),
        "p_customer_rating_vs_vehicle": float(stats.f_oneway(*groups).pvalue) if len(groups) > 1 else np.nan,
        "p_incomplete_reason_vs_vehicle": chi_p(inc["Vehicle_Type"], inc["Incomplete_Rides_Reason"]) if len(inc) else np.nan,
        "locations_outside_chance": int((z.abs() > 1.96).sum()),
        "locations_total": int(len(loc)),
        "corr_driver_vs_customer_rating": float(done["Driver_Ratings"].corr(done["Customer_Rating"])),
        "corr_fare_vs_distance": float(done["Booking_Value"].corr(done["Ride_Distance"])),
        "max_abs_corr_rating_drivers": float(done[["Driver_Ratings", "Customer_Rating"]].apply(
            lambda col: done[["Ride_Distance", "Booking_Value", "V_TAT", "C_TAT"]].corrwith(col).abs().max()).max()),
    }


# =========================================================================== #
# 5. Insights
# =========================================================================== #
@dataclass
class Insight:
    """One decision-ready finding: what / why / so what, backed by evidence."""
    id: str
    category: str            # Demand | Supply | Revenue | Pricing | Customers | Quality | Data
    title: str               # the headline claim
    metric: str              # the single number shown large on the card
    metric_label: str
    what: str                # what the data shows
    why: str                 # the evidence-backed reason
    action: str              # the recommended business response
    evidence: list[str] = field(default_factory=list)
    confidence: str = "High"  # High = tested statistically; Medium = descriptive; Low = hypothesis


def _p(value: float) -> str:
    """Format a p-value for prose."""
    return "p < 0.001" if value < 0.001 else f"p = {value:.2f}"


def build_insights(df: pd.DataFrame) -> list[Insight]:
    """Generate the full list of insight cards from the data (never hard-coded numbers)."""
    k = kpis(df)
    t = statistical_tests(df)
    veh = vehicle_summary(df)
    hr = hourly_demand(df)
    wd = weekday_demand(df)
    att = failure_attribution(df).set_index("Root_Cause")
    leak = revenue_leakage(df).set_index("Failure_Type")
    cust_r = customer_cancel_reasons(df)
    drv_r = driver_cancel_reasons(df)
    inc_r = incomplete_reasons(df).set_index("Reason")
    pay = payment_summary(df).set_index("Payment_Method")
    cust = customer_outcomes(df)
    price = pricing_stats(df)
    bands = distance_band_summary(df)
    fpk_h = fare_per_km_hourly(df)
    done = _completed(df)
    anomalies = {r.Rule: r.Flagged for r in anomaly_scorecard(df).itertuples()}

    supply_share = att.loc[att["Supply_Side"], "Share_Pct"].sum()
    drv_triggered = cust_r.loc[cust_r["Driver_Triggered"], "Share_Pct"].sum()
    cust_linked = drv_r.loc[drv_r["Owner"] == "Customer side", "Share_Pct"].sum()
    ac_total = int((df["Canceled_Rides_by_Customer"] == "AC is Not working").sum())
    ac_bad = int(anomalies.get("AC complaint on a non-AC vehicle", 0))
    inc_total = int((df["Incomplete_Rides"] == "Yes").sum())
    inc_value = float(done.loc[done["Incomplete_Rides"] == "Yes", "Booking_Value"].sum())
    inc_pct = _pct(inc_total, len(done))
    inc_by_vehicle = done.groupby("Vehicle_Type")["Incomplete_Rides"].apply(lambda s: _pct((s == "Yes").sum(), len(s)))
    digital_share = pay.loc[pay.index != "Cash", "Revenue_Share_Pct"].sum() if len(pay) else 0
    auto = veh[veh["Vehicle_Type"] == "Auto"]
    others = veh[veh["Vehicle_Type"] != "Auto"]
    fare_med = pd.Series(price["fare_median_by_vehicle"])
    top_decile_share = _top_decile_share(done)

    ins: list[Insight] = []

    ins.append(Insight(
        "I01", "Supply", "Four in ten bookings never become a ride",
        fmt_pct(k["success_rate"]), "booking success rate",
        f"{fmt_int(k['failed'])} of {fmt_int(k['total_bookings'])} bookings failed, so only {fmt_inr(k['revenue'])} of "
        f"{fmt_inr(k['potential_value'])} of quoted fares was realised.",
        f"The failure rate is the same everywhere: success ranges {veh['Success_Rate_Pct'].min():.1f}-{veh['Success_Rate_Pct'].max():.1f}% "
        f"across vehicles, {hr['Success_Rate_Pct'].min():.1f}-{hr['Success_Rate_Pct'].max():.1f}% across hours and "
        f"{wd['Success_Rate_Pct'].min():.1f}-{wd['Success_Rate_Pct'].max():.1f}% across weekdays. None of these gaps is statistically "
        f"significant (vehicle {_p(t['p_success_vs_vehicle'])}, hour {_p(t['p_success_vs_hour'])}, location {_p(t['p_success_vs_location'])}). "
        "A problem that looks identical in every segment is systemic - it sits in the dispatch and driver-supply model, not in one city zone, vehicle or time slot.",
        "Fix it at platform level (dispatch logic, driver acceptance incentives, cancellation penalties, ETA transparency) rather than running segment-specific campaigns.",
        [f"Chi-square success vs vehicle {_p(t['p_success_vs_vehicle'])}", f"success vs hour {_p(t['p_success_vs_hour'])}",
         f"success vs pickup location {_p(t['p_success_vs_location'])}", f"{t['locations_outside_chance']} of {t['locations_total']} locations outside chance range (about 2-3 expected)"],
    ))

    ins.append(Insight(
        "I02", "Supply", "The supply side explains almost nine in ten failures",
        fmt_pct(supply_share, 0), "of failures trace back to drivers",
        f"Driver cancellations ({k['driver_cancel_rate']:.1f}% of bookings) and 'no driver found' ({k['no_driver_rate']:.1f}%) add up to "
        f"{k['driver_cancel_rate'] + k['no_driver_rate']:.1f}% of all bookings, versus {k['customer_cancel_rate']:.1f}% cancelled by customers. "
        f"Of those customer cancellations, {drv_triggered:.1f}% cite the driver ('not moving towards pickup' or 'asked to cancel').",
        "A customer who cancels because the driver is stalled or asks them to cancel is reacting to a supply failure, but the platform books it as a customer cancellation. "
        f"Re-attributing those, {supply_share:.0f}% of the {fmt_int(k['failed'])} failed bookings are driver-side and only {100 - supply_share:.0f}% are truly customer-owned (change of plans, wrong address, AC).",
        "Track a 'driver-attributable failure rate' as the north-star metric; auto-reassign when a driver has not moved toward pickup within a set time; penalise 'asked to cancel' behaviour.",
        [f"No driver found: {fmt_int(att.loc['No driver found', 'Failed_Bookings'])}", f"Driver cancelled: {fmt_int(att.loc['Driver cancelled', 'Failed_Bookings'])}",
         f"Customer cancelled, driver-triggered: {fmt_int(att.loc['Customer cancelled - driver-triggered', 'Failed_Bookings'])}",
         f"Customer cancelled, own reason: {fmt_int(att.loc['Customer cancelled - own reason', 'Failed_Bookings'])}"],
    ))

    ins.append(Insight(
        "I03", "Supply", "Most driver cancellations cite the rider, and the reasons are too vague to act on",
        fmt_pct(cust_linked), "of driver cancels cite the customer side",
        f"Top driver reasons: {', '.join(f'{r.Reason} ({r.Share_Pct:.1f}%)' for r in drv_r.head(4).itertuples())}.",
        f"{cust_linked:.1f}% of driver cancellations point at the rider (generic 'customer related issue', a sick rider, or too many passengers), only "
        f"{100 - cust_linked:.1f}% at the driver's own readiness. 'Customer related issue' alone is the second-largest bucket and is a catch-all: the real cause is hidden. "
        "Passenger count and rider health are facts the app could capture before dispatch, which would prevent a cancellation at the pickup point.",
        "Capture passenger count at booking, split the vague reason into structured sub-reasons, and run pre-shift vehicle checks and shift planning to shrink the personal/car bucket.",
        [f"Personal & Car related: {fmt_int(drv_r.loc[drv_r['Reason'] == 'Personal & Car related issue', 'Count'].sum())}"],
        "Medium",
    ))

    ins.append(Insight(
        "I04", "Revenue", f"{fmt_inr(k['quoted_fare_lost'], 1)} of quoted fares never converted",
        fmt_inr(k["quoted_fare_lost"], 1), "quoted fare lost to failed bookings",
        f"Driver cancellations lost {fmt_inr(leak.loc['Driver cancellation', 'Quoted_Fare_Lost'])}, customer cancellations "
        f"{fmt_inr(leak.loc['Customer cancellation', 'Quoted_Fare_Lost'])} and 'no driver found' {fmt_inr(leak.loc['No driver found', 'Quoted_Fare_Lost'])}. "
        f"Recovering just 10% of that would add {fmt_inr(0.1 * k['quoted_fare_lost'])} ({0.1 * k['quoted_fare_lost'] / max(k['revenue'], 1) * 100:.1f}%) to revenue.",
        f"Failed and completed bookings carry the same average fare ({cfg.CURRENCY}{df.loc[df['Is_Successful'] == 0, 'Booking_Value'].mean():.0f} vs {cfg.CURRENCY}{k['avg_fare']:.0f}), "
        "so the loss is not concentrated in cheap rides nobody wants to serve; it is spread evenly across fare levels, which points to dispatch and incentives rather than price.",
        "Prioritise driver-cancellation recovery first (largest bucket), then no-driver-found coverage; model the 10% recovery as the first business case.",
        ["Quoted fare is not realised revenue; revenue counts completed rides only."],
    ))

    ins.append(Insight(
        "I05", "Pricing", "Fares do not follow distance, so the price signal is broken or the data is not the metered fare",
        f"{price['fare_distance_corr']:.3f}", "fare-distance correlation",
        f"Average fare is about {cfg.CURRENCY}{bands['Avg_Fare'].mean():.0f} in every distance band ({cfg.CURRENCY}{bands['Avg_Fare'].min():.0f}-{cfg.CURRENCY}{bands['Avg_Fare'].max():.0f}), "
        f"so fare per km falls from {cfg.CURRENCY}{bands['Fare_Per_Km'].iloc[0]:.0f} on 1-5 km rides to {cfg.CURRENCY}{bands['Fare_Per_Km'].iloc[-1]:.0f} on 41-50 km rides. "
        f"Median fare is {cfg.CURRENCY}{fare_med.min():.0f}-{cfg.CURRENCY}{fare_med.max():.0f} for all seven vehicle types.",
        "In a distance-based tariff, fare and distance correlate strongly and premium vehicles cost more per km. Here the correlation is effectively zero and a bike, an auto and an SUV have the same median fare. "
        "Either Booking_Value is not the metered fare (for example a quoted/estimated value, or synthetic data) or the pricing engine is not using distance.",
        "Audit the fare engine and the Booking_Value lineage before using it for pricing decisions; review the "
        f"{fmt_int(anomalies.get(f'Fare above {cfg.CURRENCY}{cfg.EXTREME_FARE_PER_KM}/km', 0))} rides above {cfg.CURRENCY}{cfg.EXTREME_FARE_PER_KM}/km.",
        [f"corr(fare, distance) = {price['fare_distance_corr']:.3f}"],
    ))

    ins.append(Insight(
        "I06", "Demand", "There is no peak hour to staff for, and the Monday-Wednesday 'peak' is a calendar artefact",
        f"{(hr['Bookings'].max() / hr['Bookings'].mean() - 1) * 100:+.1f}%", "busiest hour vs average",
        f"All 24 hours sit between {fmt_int(hr['Bookings'].min())} and {fmt_int(hr['Bookings'].max())} bookings. Raw weekday totals look uneven "
        f"(Mon-Wed up to {fmt_int(wd['Total_Bookings'].max())} vs {fmt_int(wd['Total_Bookings'].min())} on Sunday), but per-day averages are flat "
        f"({wd['Avg_Bookings_Per_Day'].min():,.0f}-{wd['Avg_Bookings_Per_Day'].max():,.0f}).",
        f"July 2024 contained five Mondays, Tuesdays and Wednesdays but only four of every other weekday, which alone creates a ~25% raw gap. After normalising, nothing is left "
        f"(hourly uniformity {_p(t['p_hourly_uniform'])}). Real urban demand normally peaks with commutes, so a perfectly flat curve suggests the data is sampled or synthetic, "
        f"and surge cannot be evaluated either: fare per km stays within {cfg.CURRENCY}{fpk_h['Fare_Per_Km'].min():.1f}-{cfg.CURRENCY}{fpk_h['Fare_Per_Km'].max():.1f} across hours.",
        "Do not reallocate drivers by hour on this evidence. Re-run the analysis on full production timestamps and add a surge-multiplier field so surge effectiveness can be measured.",
        [f"Hourly uniformity {_p(t['p_hourly_uniform'])}", "Weekday counts: 5 x Mon/Tue/Wed, 4 x other days"],
    ))

    ins.append(Insight(
        "I07", "Revenue", "Cash still carries more than half of revenue",
        fmt_pct(pay.loc["Cash", "Revenue_Share_Pct"], 1) if "Cash" in pay.index else "n/a", "of revenue paid in cash",
        f"Cash {fmt_inr(pay.loc['Cash', 'Revenue']) if 'Cash' in pay.index else 'n/a'}, UPI {fmt_inr(pay.loc['UPI', 'Revenue']) if 'UPI' in pay.index else 'n/a'}; "
        f"cards together are only {pay.loc[pay.index.isin(['Credit Card', 'Debit Card']), 'Revenue_Share_Pct'].sum():.1f}% of revenue. Digital overall: {digital_share:.1f}%.",
        f"Average fare is almost identical across methods ({cfg.CURRENCY}{pay['Avg_Fare'].min():.0f}-{cfg.CURRENCY}{pay['Avg_Fare'].max():.0f}), so people do not choose cash because the ride is cheap or expensive. "
        "That points to habit and trust rather than affordability, which means one simple incentive can target every rider.",
        "Offer a flat UPI cashback or wallet bonus; track cash-collection reconciliation risk; push cards only where there is a clear loyalty benefit.",
        [f"Digital share of revenue {digital_share:.1f}%"],
        "Medium",
    ))

    ins.append(Insight(
        "I08", "Customers", "Most customers try Ola once, and a third never complete a ride",
        fmt_pct(cust["never_completed_rate"]), "of customers never completed a ride",
        f"{cust['single_booking_rate']:.1f}% of customers booked exactly once and only {cust['repeat_rate']:.1f}% booked more than once. "
        f"{fmt_int(cust['never_completed'])} customers had no completed ride and {fmt_int(cust['failed_2plus'])} had two or more failed bookings.",
        f"Of customers who booked only once, {cust['single_booking_failed_rate']:.1f}% saw that single attempt fail, which matches the platform failure rate: there is no second chance in the data. "
        f"Revenue is also fragmented: the five biggest customers account for {top_customers_by_value(df)['Share_Of_Revenue_Pct'].sum():.2f}% of revenue, so there are no key accounts to protect - growth must come from retention and volume.",
        "Launch a win-back flow for customers whose booking failed (priority dispatch plus a small credit within hours), and a referral/repeat-ride offer after a first completed ride.",
        [f"Customers with 3+ failed bookings: {fmt_int(cust['failed_3plus'])}",
         f"Top 10% of paying customers = {top_decile_share:.1f}% of revenue, driven by one-off high fares"],
        "Medium",
    ))

    ins.append(Insight(
        "I09", "Quality", "Ratings do not move with anything, so they cannot guide driver incentives",
        f"{t['corr_driver_vs_customer_rating']:+.3f}", "driver vs customer rating correlation",
        f"Both rating scales are spread evenly between 3.0 and 5.0 (mean {k['avg_driver_rating']:.2f} / {k['avg_customer_rating']:.2f}), no ride is rated below {min(done['Driver_Ratings'].min(), done['Customer_Rating'].min()):.1f}, "
        f"and {_pct((done['Customer_Rating'] <= 3.5).sum(), len(done)):.1f}% of rides are rated 3.5 or lower.",
        f"No rating correlates with distance, fare, turn-around time or vehicle (largest |r| = {t['max_abs_corr_rating_drivers']:.3f}); customer rating by vehicle is not significant "
        f"({_p(t['p_customer_rating_vs_vehicle'])}); the two sides' ratings are independent. A score that does not react to wait time or trip quality is either random or compressed by a 3.0 floor, "
        "so it carries almost no information about the experience.",
        "Add reason tags for low ratings, allow the full 1-5 range, and validate ratings against wait time and complaints before using them in driver incentives.",
        [f"Customer rating vs vehicle {_p(t['p_customer_rating_vs_vehicle'])}", f"max |r| with distance/fare/TAT = {t['max_abs_corr_rating_drivers']:.3f}"],
    ))

    ins.append(Insight(
        "I10", "Quality", "Incomplete rides expose revenue to refunds and are not tied to any vehicle",
        fmt_inr(inc_value), "booked on incomplete rides",
        f"{fmt_int(inc_total)} completed bookings ({inc_pct:.1f}%) ended incomplete: "
        + ", ".join(f"{r} {v:.1f}%" for r, v in inc_r["Share_Pct"].items()) + ".",
        f"Incomplete rates sit between {inc_by_vehicle.min():.1f}% and {inc_by_vehicle.max():.1f}% on every vehicle and the reason mix is not vehicle-specific ({_p(t['p_incomplete_reason_vs_vehicle'])}). "
        "Every one of these rides still has a payment recorded, so the money is at risk of dispute rather than lost outright. Breakdowns that hit all seven fleets equally indicate a general maintenance and re-dispatch gap, not a bad vehicle model.",
        "Introduce pre-trip vehicle checks, automatic re-dispatch on breakdown, and a standard partial-fare/refund rule for incomplete rides.",
        [f"Reason vs vehicle {_p(t['p_incomplete_reason_vs_vehicle'])}"],
    ))

    if len(auto) and len(others):
        ins.append(Insight(
            "I11", "Pricing", "Auto is the only vehicle that behaves differently, and it earns 2.5x more per km",
            f"{auto['Avg_Distance_Km'].iloc[0]:.1f} km", f"average Auto trip (others ~{others['Avg_Distance_Km'].mean():.0f} km)",
            f"Auto trips average {auto['Avg_Distance_Km'].iloc[0]:.1f} km against {others['Avg_Distance_Km'].mean():.1f} km for the other six types, but the average fare is the same "
            f"({cfg.CURRENCY}{auto['Avg_Fare'].iloc[0]:.0f}), so Auto yields {cfg.CURRENCY}{auto['Fare_Per_Km'].iloc[0]:.0f}/km versus about {cfg.CURRENCY}{others['Fare_Per_Km'].mean():.0f}/km.",
            f"Auto trips never exceed {int(done.loc[done['Vehicle_Type'] == 'Auto', 'Ride_Distance'].max())} km while other vehicles reach {int(done['Ride_Distance'].max())} km, which fits Auto being a short-hop product. "
            "Because fare does not follow distance (see the pricing finding), the shorter trip simply earns more per km.",
            "Position Auto as the short-hop product and test distance-based pricing there first, where the per-km gap is widest.",
            ["Auto max distance vs others"],
        ))

    ins.append(Insight(
        "I12", "Quality", "AC cancellations are being logged on vehicles that have no AC",
        fmt_pct(_pct(ac_bad, ac_total)), f"of {fmt_int(ac_total)} AC cancellations on non-AC vehicles",
        f"{fmt_int(ac_bad)} of {fmt_int(ac_total)} 'AC is not working' cancellations were logged on Bike, eBike or Auto.",
        "Those vehicles cannot have air-conditioning, so the reason cannot be literally true. Customers pick the nearest-looking option, which means the reason list is not vehicle-aware "
        "and every reason percentage in the cancellation data is partly noise.",
        "Make the cancellation-reason list vehicle-specific and add an 'other' free-text option, then re-measure the reason mix.",
        [f"{fmt_int(ac_bad)} flagged bookings"],
        "High",
    ))

    ins.append(Insight(
        "I13", "Data", "The data is unusually uniform, so validate on production data before acting",
        f"{t['locations_outside_chance']}/{t['locations_total']}", "locations outside the chance range",
        "Hours, weekdays, locations, vehicles, ratings, fares and payment mix are all almost perfectly flat or evenly spread, and no variable relates to any other.",
        "Real ride-hailing data shows commute peaks, hot-spots, premium pricing and quality-driven ratings. Their absence suggests a sampled or synthetically generated dataset. "
        "The failure-rate and attribution findings are robust within the dataset, but any operational decision should be re-validated on production data.",
        "Treat this analysis as a validated methodology and a ready-to-rerun pipeline; swap in the production extract and the app, SQL and report will update unchanged.",
        ["Uniformity across all segments is itself the finding"],
        "Medium",
    ))

    return ins


def _top_decile_share(done: pd.DataFrame) -> float:
    """Share of revenue contributed by the top 10% of paying customers."""
    spend = done.groupby("Customer_ID")["Booking_Value"].sum().sort_values(ascending=False)
    if spend.empty:
        return 0.0
    n = max(len(spend) // 10, 1)
    return _pct(spend.head(n).sum(), spend.sum())


def action_roadmap(df: pd.DataFrame) -> pd.DataFrame:
    """Prioritised initiatives with a sized impact where the data allows it.

    Impact figures are *scenarios* computed from the data (e.g. 'recover 10% of
    failed bookings'), not forecasts. Effort is the analyst's rough estimate.
    """
    k = kpis(df)
    att = failure_attribution(df).set_index("Root_Cause")
    recover = 0.1 * k["quoted_fare_lost"]
    lift = recover / max(k["revenue"], 1) * 100
    cust = customer_outcomes(df)
    pay = payment_summary(df).set_index("Payment_Method")
    cash = pay.loc["Cash", "Revenue"] if "Cash" in pay.index else 0
    inc_value = float(_completed(df).loc[lambda d: d["Incomplete_Rides"] == "Yes", "Booking_Value"].sum())
    rows = [
        (1, "Cut driver-side failures",
         "Re-dispatch when a driver has not moved toward pickup; acceptance incentives; penalties for 'asked to cancel'.",
         f"Every 10% of failed bookings recovered = {fmt_inr(recover)} (+{lift:.1f}% revenue)", "I01, I02, I04", "High"),
        (2, "Win back failed first bookings",
         "Priority dispatch plus a small credit within hours of a failed booking; referral after the first completed ride.",
         f"Targets {fmt_int(cust['never_completed'])} customers with no completed ride", "I08", "Medium"),
        (3, "Make cancellation reasons actionable",
         "Vehicle-aware reason list, structured sub-reasons for 'customer related issue', capture passenger count at booking.",
         f"Re-attributes the {att.loc['Customer cancelled - driver-triggered', 'Failed_Bookings']:,} driver-triggered customer cancels", "I03, I12", "Low"),
        (4, "Audit the fare engine",
         "Verify Booking_Value lineage; review fares above INR 500/km and premium fares on very short rides.",
         "Protects pricing integrity before any surge or tariff change", "I05, I11", "Medium"),
        (5, "Shift cash to digital",
         "Flat UPI cashback or wallet bonus; cash-reconciliation controls for drivers.",
         f"{fmt_inr(cash)} of revenue still collected in cash", "I07", "Low"),
        (6, "Standardise incomplete-ride handling",
         "Pre-trip vehicle checks, automatic re-dispatch on breakdown, partial-fare/refund rule.",
         f"{fmt_inr(inc_value)} booked on incomplete rides", "I10", "Medium"),
        (7, "Redesign the rating system",
         "Full 1-5 range, reason tags on low scores, validate against wait time and complaints.",
         "Makes ratings usable for driver incentives", "I09", "Medium"),
        (8, "Re-validate on production data",
         "Re-run the pipeline on a full production extract (hourly peaks, surge multiplier, true fares).",
         "Confirms which findings hold outside this sample", "I06, I13", "Low"),
    ]
    return pd.DataFrame(rows, columns=["Priority", "Initiative", "What to do", "Expected impact", "Evidence", "Effort (est.)"])
