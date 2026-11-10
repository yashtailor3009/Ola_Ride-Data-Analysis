"""
ola.config
==========
Single place for every constant used across the project: file paths, the brand
palette, business-rule thresholds and static reference data (vehicle metadata).

Keeping these here means the Streamlit app, the SQL engine, the report builders
and the tests all agree on the same names, colours and thresholds.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ASSETS_DIR = ROOT_DIR / "assets"
SQL_DIR = ROOT_DIR / "sql"

CLEAN_DATA_PATH = DATA_DIR / "ola_rides_clean.csv.gz"
DQ_REPORT_PATH = DATA_DIR / "data_quality_report.json"
QUERIES_SQL_PATH = SQL_DIR / "ola_queries.sql"
SCHEMA_SQL_PATH = SQL_DIR / "ola_schema_and_cleaning.sql"

APP_TITLE = "Ola Ride Insights"
APP_SUBTITLE = "Ride-sharing & mobility analytics · July 2024"
CURRENCY = "₹"

# --------------------------------------------------------------------------- #
# Brand palette (shared by Streamlit, matplotlib report, PPT and Power BI theme)
# --------------------------------------------------------------------------- #
INK = "#0F1A17"        # deep green-black: text, sidebar
LIME = "#C6E22A"       # brand accent
PAPER = "#F4F6F1"      # app canvas
CARD = "#FFFFFF"
MUTED = "#5E6B66"
GRID = "#E3E8DF"

# Semantic colours for the four booking outcomes - used identically everywhere.
STATUS_COLORS = {
    "Success": "#1F9D6B",
    "Canceled by Customer": "#F2A93B",
    "Canceled by Driver": "#E4572E",
    "Driver Not Found": "#6B7A99",
}

# One stable colour per vehicle type.
VEHICLE_COLORS = {
    "Auto": "#F2A93B",
    "Bike": "#3D5A80",
    "eBike": "#1F9D6B",
    "Mini": "#8E7DBE",
    "Prime Plus": "#E4572E",
    "Prime Sedan": "#0F1A17",
    "Prime SUV": "#2A9D8F",
}

PAYMENT_COLORS = {
    "Cash": "#F2A93B",
    "UPI": "#1F9D6B",
    "Credit Card": "#3D5A80",
    "Debit Card": "#8E7DBE",
}

# --------------------------------------------------------------------------- #
# Reference data (from the 'Sheet2' lookup in the source workbook)
# --------------------------------------------------------------------------- #
VEHICLE_ICONS = {
    "Prime Sedan": "https://cdn-icons-png.flaticon.com/128/14183/14183770.png",
    "Bike": "https://cdn-icons-png.flaticon.com/128/9983/9983173.png",
    "Prime SUV": "https://cdn-icons-png.flaticon.com/128/9983/9983204.png",
    "eBike": "https://cdn-icons-png.flaticon.com/128/6839/6839867.png",
    "Mini": "https://cdn-icons-png.flaticon.com/128/3202/3202926.png",
    "Prime Plus": "https://cdn-icons-png.flaticon.com/128/11409/11409716.png",
    "Auto": "https://cdn-icons-png.flaticon.com/128/16526/16526595.png",
}

# Analyst-defined grouping (assumption, documented in README): used for the
# vehicle-class JOIN examples and the "segment" analysis.
VEHICLE_CLASS = {
    "Bike": "Two-wheeler",
    "eBike": "Two-wheeler",
    "Auto": "Three-wheeler",
    "Mini": "Cab",
    "Prime Sedan": "Cab",
    "Prime Plus": "Cab",
    "Prime SUV": "Cab",
}

# Vehicles that physically cannot have air-conditioning. An "AC is Not working"
# cancellation on one of these is logically inconsistent -> anomaly rule.
NON_AC_VEHICLES = ("Bike", "eBike", "Auto")

# --------------------------------------------------------------------------- #
# Business rules / thresholds
# --------------------------------------------------------------------------- #
DRIVER_TRIGGERED_CUSTOMER_REASONS = (
    "Driver is not moving towards pickup location",
    "Driver asked to cancel",
)
EXTREME_FARE_PER_KM = 500          # INR per km on a completed ride
HIGH_FARE_SHORT_RIDE = (1500, 5)   # (min fare INR, max distance km)
RATING_MISMATCH_GAP = 1.5          # |driver - customer| rating gap
REPEAT_FAILURE_THRESHOLD = 3       # failed attempts by one customer

TIME_BANDS = {                     # four equal 6-hour bands -> fair like-for-like comparison
    "Night (00-05)": list(range(0, 6)),
    "Morning (06-11)": list(range(6, 12)),
    "Afternoon (12-17)": list(range(12, 18)),
    "Evening (18-23)": list(range(18, 24)),
}
DISTANCE_BANDS = [0, 5, 10, 20, 30, 40, 50]
DISTANCE_LABELS = ["1-5 km", "6-10 km", "11-20 km", "21-30 km", "31-40 km", "41-50 km"]

WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
STATUS_ORDER = ["Success", "Canceled by Customer", "Canceled by Driver", "Driver Not Found"]
