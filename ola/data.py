"""
ola.data
========
Loading the cleaned dataset and applying the sidebar filters.
Pure pandas - no Streamlit - so the same code is used by tests and scripts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from . import config as cfg

DAY_TYPES = ("All days", "Weekdays only", "Weekends only")


@dataclass(frozen=True)
class Filters:
    """The user's current sidebar selection. Empty tuples mean 'no restriction'."""
    start: date
    end: date
    vehicles: tuple[str, ...] = ()
    time_bands: tuple[str, ...] = ()
    day_type: str = DAY_TYPES[0]
    pickups: tuple[str, ...] = ()


def load_clean(path: Path = cfg.CLEAN_DATA_PATH) -> pd.DataFrame:
    """Read the cleaned CSV (gzip) with correct dtypes."""
    if not Path(path).exists():
        raise FileNotFoundError(
            f"{path} not found. Build it with:  python -m ola.preprocessing --raw OLA_DataSet.xlsx")
    return pd.read_csv(path, parse_dates=["Date", "Booking_Datetime"])


def load_dq_report(path: Path = cfg.DQ_REPORT_PATH) -> dict:
    """Read the data-quality report written by the preprocessing step."""
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}


def default_filters(df: pd.DataFrame) -> Filters:
    """A filter object that selects everything."""
    return Filters(start=df["Date"].min().date(), end=df["Date"].max().date())


def apply_filters(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    """Return the rows matching ``f`` (a new frame; the input is untouched)."""
    mask = df["Date"].between(pd.Timestamp(f.start), pd.Timestamp(f.end))
    if f.vehicles:
        mask &= df["Vehicle_Type"].isin(f.vehicles)
    if f.time_bands:
        mask &= df["Time_Band"].isin(f.time_bands)
    if f.day_type == DAY_TYPES[1]:
        mask &= df["Is_Weekend"] == 0
    elif f.day_type == DAY_TYPES[2]:
        mask &= df["Is_Weekend"] == 1
    if f.pickups:
        mask &= df["Pickup_Location"].isin(f.pickups)
    return df[mask]


def describe_filters(f: Filters, shown: int, total: int) -> str:
    """One-line summary for the page header, e.g. '12,300 of 103,024 bookings · 1-15 Jul'."""
    parts = [f"{shown:,} of {total:,} bookings", f"{f.start:%d %b} - {f.end:%d %b %Y}"]
    if f.vehicles:
        parts.append(f"{len(f.vehicles)} vehicle type(s)")
    if f.time_bands:
        parts.append(f"{len(f.time_bands)} time band(s)")
    if f.day_type != DAY_TYPES[0]:
        parts.append(f.day_type.lower())
    if f.pickups:
        parts.append(f"{len(f.pickups)} pickup area(s)")
    return "  ·  ".join(parts)
