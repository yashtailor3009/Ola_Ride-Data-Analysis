"""
scripts/export_deck_data.py - writes reports/deck_data.json for scripts/build_pptx.js.
All slide numbers come from ola.metrics, so the deck always matches the app, SQL and PDF.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ola import config as cfg                      # noqa: E402
from ola import metrics as m                       # noqa: E402
from ola.data import load_clean                    # noqa: E402


def build() -> dict:
    df = load_clean()
    k, done = m.kpis(df), df[df["Is_Successful"] == 1]
    daily, hr, wd = m.daily_volume(df), m.hourly_demand(df), m.weekday_demand(df)
    att, leak = m.failure_attribution(df), m.revenue_leakage(df).set_index("Failure_Type")
    cr, dr = m.customer_cancel_reasons(df), m.driver_cancel_reasons(df)
    pay, freq, rd = m.payment_summary(df), m.customer_frequency(df), m.rating_distribution(df)
    cust, score, road = m.customer_outcomes(df), m.anomaly_scorecard(df), m.action_roadmap(df)
    veh, bands, tests = m.vehicle_summary(df), m.distance_band_summary(df), m.statistical_tests(df)
    sample = done.sample(450, random_state=11)
    supply = float(att.loc[att["Supply_Side"], "Share_Pct"].sum())
    auto = veh[veh["Vehicle_Type"] == "Auto"].iloc[0]
    others = veh[veh["Vehicle_Type"] != "Auto"]
    return {
        "kpi": {**{x: (float(v) if not isinstance(v, int) else v) for x, v in k.items()},
                "supply_share": supply, "recover10": 0.1 * k["quoted_fare_lost"],
                "recover10_pct": 0.1 * k["quoted_fare_lost"] / k["revenue"] * 100},
        "cust": cust,
        "daily": {"labels": [d.strftime("%d %b") for d in daily["Date"]], "bookings": daily["Bookings"].tolist(),
                  "avg7": [round(x, 1) for x in daily["Bookings_7d_Avg"]], "mean": float(daily["Bookings"].mean()),
                  "cv": float(daily["Bookings"].std() / daily["Bookings"].mean() * 100)},
        "hourly": {"labels": [str(h) for h in hr["Ride_Hour"]], "values": hr["Bookings"].tolist(), "mean": float(hr["Bookings"].mean()),
                   "spread": float(max(hr["Bookings"].max() / hr["Bookings"].mean() - 1, 1 - hr["Bookings"].min() / hr["Bookings"].mean()) * 100)},
        "weekday": {"labels": [n[:3] for n in wd["Day_Name"]], "perday": [round(x) for x in wd["Avg_Bookings_Per_Day"]],
                    "total": wd["Total_Bookings"].tolist()},
        "status": {"labels": m.status_breakdown(df)["Booking_Status"].tolist(), "values": m.status_breakdown(df)["Bookings"].tolist()},
        "attribution": {"labels": att["Root_Cause"].tolist(), "values": att["Failed_Bookings"].tolist(), "share": att["Share_Pct"].round(1).tolist()},
        "cust_reasons": {"labels": cr["Reason"].tolist(), "values": cr["Count"].tolist(), "share": cr["Share_Pct"].round(1).tolist(),
                         "driver_triggered": float(cr.loc[cr["Driver_Triggered"], "Share_Pct"].sum())},
        "drv_reasons": {"labels": dr["Reason"].tolist(), "values": dr["Count"].tolist(), "share": dr["Share_Pct"].round(1).tolist(),
                        "rider_side": float(dr.loc[dr["Owner"] == "Customer side", "Share_Pct"].sum())},
        "leak": {"driver": float(leak.loc["Driver cancellation", "Quoted_Fare_Lost"]), "customer": float(leak.loc["Customer cancellation", "Quoted_Fare_Lost"]),
                 "nodriver": float(leak.loc["No driver found", "Quoted_Fare_Lost"])},
        "pricing": {"x": sample["Ride_Distance"].tolist(), "y": sample["Booking_Value"].tolist(), "corr": tests["corr_fare_vs_distance"],
                    "band_avg_fare": [round(x) for x in bands["Avg_Fare"]], "band_fpk": [round(x) for x in bands["Fare_Per_Km"]],
                    "auto_fpk": float(auto["Fare_Per_Km"]), "others_fpk": float(others["Fare_Per_Km"].mean()),
                    "auto_km": float(auto["Avg_Distance_Km"]), "others_km": float(others["Avg_Distance_Km"].mean()),
                    "avg_fare": float(done["Booking_Value"].mean())},
        "payments": {"labels": pay["Payment_Method"].tolist(), "values": [round(v / 1e6, 2) for v in pay["Revenue"]], "share": pay["Revenue_Share_Pct"].round(1).tolist()},
        "freq": {"labels": freq["Bookings_Per_Customer"].astype(str).tolist(), "values": freq["Customers"].tolist(), "share": freq["Share_Pct"].round(1).tolist()},
        "ratings": {"labels": [f"{r:.1f}" for r in rd["Rating"]], "driver": rd["Driver"].tolist(), "customer": rd["Customer"].tolist(),
                    "corr": tests["corr_driver_vs_customer_rating"], "low_pct": float((done["Customer_Rating"] <= 3.5).mean() * 100)},
        "tests": {"p_vehicle": tests["p_success_vs_vehicle"], "p_hour": tests["p_success_vs_hour"], "p_hourly_uniform": tests["p_hourly_uniform"],
                  "succ_min": float(veh["Success_Rate_Pct"].min()), "succ_max": float(veh["Success_Rate_Pct"].max())},
        "anomalies": {"labels": score["Rule"].tolist(), "values": score["Flagged"].tolist(), "units": score["Unit"].tolist()},
        "roadmap": [{"p": int(r.Priority), "initiative": r.Initiative, "impact": r._4, "effort": r._6} for r in road.itertuples()],
    }


if __name__ == "__main__":
    out = ROOT / "reports" / "deck_data.json"
    out.write_text(json.dumps(build(), indent=1, default=float))
    print("wrote", out)
