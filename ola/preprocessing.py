"""
ola.preprocessing
=================
Turns the raw OLA workbook (sheet ``July``) into an analysis-ready table.

Pipeline (each step is a small, separately testable function)
-------------------------------------------------------------
1. ``load_raw``          - read columns A:S only (drops the helper "Vehicle Images" column)
2. ``standardise_text``  - trim whitespace, collapse repeated spaces
3. ``convert_types``     - proper date / numeric dtypes; the literal string ``'null'`` -> NaN
4. ``add_features``      - derived columns used by SQL, Power BI and the app
5. ``validate``          - business-rule checks that prove the cleaning is correct
6. ``build_dq_report``   - JSON report (counts, rules, caveats) shipped with the data

Design decision - **missing values are NOT imputed**.
In this dataset a ``null`` is *structural*, not accidental: ratings, payment
method and turn-around times exist only for completed rides; cancellation
reasons exist only for the matching cancellation status. Filling them with a
mean/mode would fabricate ratings for rides that never happened and corrupt
every average. They are kept as NULL so SQL aggregates skip them correctly.

Run from the command line::

    python -m ola.preprocessing --raw OLA_DataSet.xlsx
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as cfg

# Columns we keep from the workbook (A:S). Column T ("Vehicle Images") is an
# Excel XLOOKUP helper, reproduced in config.VEHICLE_ICONS instead.
RAW_COLUMNS = [
    "Date", "Time", "Booking_ID", "Booking_Status", "Customer_ID", "Vehicle_Type",
    "Pickup_Location", "Drop_Location", "V_TAT", "C_TAT",
    "Canceled_Rides_by_Customer", "Canceled_Rides_by_Driver",
    "Incomplete_Rides", "Incomplete_Rides_Reason", "Booking_Value",
    "Payment_Method", "Ride_Distance", "Driver_Ratings", "Customer_Rating",
]
NULL_TOKENS = ["null", "NULL", "Null", "", "NA", "N/A", "nan", "NaN"]

# Final column order of the cleaned table (also the order of the SQL table).
CLEAN_COLUMNS = [
    "Booking_ID", "Customer_ID", "Date", "Time", "Booking_Datetime", "Ride_Hour",
    "Day_Name", "Day_Of_Week_No", "Is_Weekend", "Time_Band",
    "Booking_Status", "Is_Successful", "Is_Cancelled", "Failure_Type", "Failure_Reason",
    "Vehicle_Type", "Pickup_Location", "Drop_Location", "Is_Same_Pickup_Drop",
    "V_TAT", "C_TAT", "Canceled_Rides_by_Customer", "Canceled_Rides_by_Driver",
    "Incomplete_Rides", "Incomplete_Rides_Reason", "Booking_Value", "Payment_Method",
    "Ride_Distance", "Distance_Band", "Fare_Per_Km", "Driver_Ratings",
    "Customer_Rating", "Rating_Gap",
]


# --------------------------------------------------------------------------- #
# 1. Load
# --------------------------------------------------------------------------- #
def load_raw(path: str | Path, sheet: str = "July") -> pd.DataFrame:
    """Read the raw sheet, keeping only the 19 documented columns.

    ``na_values`` converts the workbook's literal ``'null'`` strings to NaN at
    read time so no downstream step has to special-case them.
    """
    df = pd.read_excel(
        path, sheet_name=sheet, usecols=range(len(RAW_COLUMNS)),
        na_values=NULL_TOKENS, keep_default_na=False,
    )
    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Raw sheet is missing expected columns: {sorted(missing)}")
    return df[RAW_COLUMNS].copy()


# --------------------------------------------------------------------------- #
# 2. Standardise text
# --------------------------------------------------------------------------- #
def standardise_text(df: pd.DataFrame) -> pd.DataFrame:
    """Trim and collapse whitespace in every text column.

    The source data is already tidy (0 whitespace issues were found), but the
    step is kept so the pipeline stays safe if a later month arrives dirty.
    """
    out = df.copy()
    text_cols = [c for c in out.columns if pd.api.types.is_string_dtype(out[c]) or out[c].dtype == object]
    for col in text_cols:
        if col == "Time":            # datetime.time objects, handled in convert_types
            continue
        s = out[col]
        mask = s.notna()
        out.loc[mask, col] = (
            s[mask].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
        )
    return out


# --------------------------------------------------------------------------- #
# 3. Types
# --------------------------------------------------------------------------- #
def convert_types(df: pd.DataFrame) -> pd.DataFrame:
    """Cast every column to its proper dtype.

    ``Date`` in the workbook already carries the clock time, and equals
    ``Date`` + ``Time`` for 100 % of rows (verified), so:
    * ``Booking_Datetime`` <- full timestamp
    * ``Date``             <- calendar date only
    * ``Time``             <- ``HH:MM:SS`` text
    """
    out = df.copy()
    stamp = pd.to_datetime(out["Date"], errors="coerce")
    out["Booking_Datetime"] = stamp
    out["Date"] = stamp.dt.normalize()
    out["Time"] = stamp.dt.strftime("%H:%M:%S")

    for col in ["V_TAT", "C_TAT", "Driver_Ratings", "Customer_Rating"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ["Booking_Value", "Ride_Distance"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    return out


# --------------------------------------------------------------------------- #
# 4. Feature engineering
# --------------------------------------------------------------------------- #
def _hour_to_band() -> dict[int, str]:
    """Invert config.TIME_BANDS into an hour -> band lookup."""
    return {h: band for band, hours in cfg.TIME_BANDS.items() for h in hours}


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create the derived columns used by SQL, Power BI and the Streamlit app."""
    out = df.copy()
    ts = out["Booking_Datetime"]

    # --- calendar features -------------------------------------------------
    out["Ride_Hour"] = ts.dt.hour.astype("int64")
    out["Day_Name"] = ts.dt.day_name()
    out["Day_Of_Week_No"] = ts.dt.dayofweek + 1            # 1 = Monday ... 7 = Sunday
    out["Is_Weekend"] = (out["Day_Of_Week_No"] >= 6).astype("int64")
    out["Time_Band"] = out["Ride_Hour"].map(_hour_to_band())

    # --- outcome flags -----------------------------------------------------
    status = out["Booking_Status"]
    out["Is_Successful"] = status.eq("Success").astype("int64")
    out["Is_Cancelled"] = status.isin(["Canceled by Customer", "Canceled by Driver"]).astype("int64")
    out["Failure_Type"] = status.map({
        "Canceled by Customer": "Customer cancellation",
        "Canceled by Driver": "Driver cancellation",
        "Driver Not Found": "No driver found",
    })
    # One unified reason column so charts do not need three separate fields.
    out["Failure_Reason"] = (
        out["Canceled_Rides_by_Customer"]
        .fillna(out["Canceled_Rides_by_Driver"])
        .fillna(status.where(status.eq("Driver Not Found")))
    )

    # --- route / pricing features -----------------------------------------
    out["Is_Same_Pickup_Drop"] = out["Pickup_Location"].eq(out["Drop_Location"]).astype("int64")
    completed = out["Is_Successful"].eq(1) & out["Ride_Distance"].gt(0)
    dist = out["Ride_Distance"].astype("float64")
    out["Fare_Per_Km"] = np.where(completed, out["Booking_Value"].astype("float64") / dist, np.nan).round(2)
    out["Distance_Band"] = pd.cut(
        dist.where(completed), bins=cfg.DISTANCE_BANDS, labels=cfg.DISTANCE_LABELS
    ).astype("object")
    out.loc[~completed, "Distance_Band"] = "Not completed"

    # --- rating features ---------------------------------------------------
    out["Rating_Gap"] = (out["Driver_Ratings"] - out["Customer_Rating"]).round(1)

    return out[CLEAN_COLUMNS]


# --------------------------------------------------------------------------- #
# 5. Validation
# --------------------------------------------------------------------------- #
def validate(df: pd.DataFrame) -> dict[str, int]:
    """Return ``{rule: number_of_violations}``. Every value should be 0.

    These rules encode what the business says must be true of the data; if the
    cleaning logic or a future data drop breaks any of them, tests fail loudly.
    """
    ok = df["Is_Successful"].eq(1)
    return {
        "duplicate_booking_id": int(df["Booking_ID"].duplicated().sum()),
        "missing_key_fields": int(df[["Booking_ID", "Customer_ID", "Booking_Status",
                                      "Vehicle_Type", "Booking_Datetime"]].isna().any(axis=1).sum()),
        "unknown_status": int((~df["Booking_Status"].isin(cfg.STATUS_ORDER)).sum()),
        "unknown_vehicle": int((~df["Vehicle_Type"].isin(cfg.VEHICLE_ICONS)).sum()),
        "success_missing_rating_or_payment": int(
            (ok & df[["Driver_Ratings", "Customer_Rating", "Payment_Method", "V_TAT", "C_TAT"]].isna().any(axis=1)).sum()),
        "failed_with_rating_or_payment": int(
            (~ok & df[["Driver_Ratings", "Customer_Rating", "Payment_Method", "V_TAT", "C_TAT"]].notna().any(axis=1)).sum()),
        "failed_with_distance": int((~ok & df["Ride_Distance"].gt(0)).sum()),
        "success_with_zero_distance": int((ok & df["Ride_Distance"].le(0)).sum()),
        "customer_cancel_reason_mismatch": int(
            (df["Booking_Status"].eq("Canceled by Customer") != df["Canceled_Rides_by_Customer"].notna()).sum()),
        "driver_cancel_reason_mismatch": int(
            (df["Booking_Status"].eq("Canceled by Driver") != df["Canceled_Rides_by_Driver"].notna()).sum()),
        "incomplete_flag_outside_success": int((~ok & df["Incomplete_Rides"].notna()).sum()),
        "incomplete_reason_mismatch": int(
            (df["Incomplete_Rides"].eq("Yes") != df["Incomplete_Rides_Reason"].notna()).sum()),
        "rating_out_of_range": int(
            ((df["Driver_Ratings"] < 1) | (df["Driver_Ratings"] > 5)
             | (df["Customer_Rating"] < 1) | (df["Customer_Rating"] > 5)).sum()),
        "non_positive_booking_value": int(df["Booking_Value"].le(0).sum()),
        "dates_outside_july_2024": int((~df["Date"].between("2024-07-01", "2024-07-31")).sum()),
    }


# --------------------------------------------------------------------------- #
# 6. Report
# --------------------------------------------------------------------------- #
def build_dq_report(raw: pd.DataFrame, clean: pd.DataFrame) -> dict:
    """Summarise what the cleaning did and what remains worth knowing."""
    rules = validate(clean)
    structural_nulls = {
        col: int(clean[col].isna().sum())
        for col in ["V_TAT", "C_TAT", "Canceled_Rides_by_Customer", "Canceled_Rides_by_Driver",
                    "Incomplete_Rides", "Incomplete_Rides_Reason", "Payment_Method",
                    "Driver_Ratings", "Customer_Rating"]
    }
    return {
        "rows_raw": int(len(raw)),
        "rows_clean": int(len(clean)),
        "columns_raw": int(raw.shape[1]),
        "columns_clean": int(clean.shape[1]),
        "date_range": [str(clean["Date"].min().date()), str(clean["Date"].max().date())],
        "unique_customers": int(clean["Customer_ID"].nunique()),
        "unique_pickup_locations": int(clean["Pickup_Location"].nunique()),
        "validation_rules_violations": rules,
        "all_rules_pass": all(v == 0 for v in rules.values()),
        "structural_nulls": structural_nulls,
        "cleaning_decisions": [
            "Literal 'null' strings converted to NaN/NULL at read time.",
            "Nulls are structural (depend on booking status) and were deliberately NOT imputed.",
            "Date column split into Date (calendar date), Time (HH:MM:SS) and Booking_Datetime.",
            "Text columns trimmed; categories already consistent (no spelling variants found).",
            "Helper column 'Vehicle Images' (XLOOKUP) dropped; icons kept in config.VEHICLE_ICONS.",
            "14 derived columns added (calendar, outcome flags, fare/km, distance band, rating gap).",
        ],
        "caveats": [
            "Booking_Value on failed bookings is the quoted fare, not revenue; revenue = Success only.",
            "Ride_Distance is 0 for every non-completed booking, so distance averages are reported both "
            "over all bookings (matches the workbook's AVERAGEIF) and over completed rides only.",
            "V_TAT / C_TAT units are not documented in the source; they are used as relative measures.",
            "Dataset covers a single month (July 2024): month-over-month trends cannot be computed.",
            "Distributions are unusually uniform (hour, weekday, location, rating, fare). Findings should be "
            "re-validated on production data before operational decisions.",
        ],
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def clean_pipeline(raw: pd.DataFrame) -> pd.DataFrame:
    """Run steps 2-4 on an already-loaded raw frame (used by tests and the CLI)."""
    return add_features(convert_types(standardise_text(raw)))


def run(raw_path: str | Path, out_path: Path = cfg.CLEAN_DATA_PATH,
        report_path: Path = cfg.DQ_REPORT_PATH) -> pd.DataFrame:
    """Full pipeline: load -> clean -> validate -> write CSV (gzip) + JSON report."""
    raw = load_raw(raw_path)
    clean = clean_pipeline(raw)
    report = build_dq_report(raw, clean)
    if not report["all_rules_pass"]:
        bad = {k: v for k, v in report["validation_rules_violations"].items() if v}
        raise RuntimeError(f"Validation failed: {bad}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(out_path, index=False, compression="gzip")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return clean


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean the OLA ride workbook.")
    parser.add_argument("--raw", required=True, help="Path to OLA_DataSet.xlsx")
    args = parser.parse_args()
    clean = run(args.raw)
    print(f"Cleaned {len(clean):,} rows x {clean.shape[1]} columns -> {cfg.CLEAN_DATA_PATH}")


if __name__ == "__main__":
    main()
