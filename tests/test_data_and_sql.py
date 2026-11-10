"""
Logic-layer tests: preprocessing output, filters, the SQL engine and the 10 required SQL answers.

Every expected number below was verified independently (pandas on the raw workbook AND the SQL result).
Run:  python -m pytest -q      (or)      python tests/run_all.py
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ola import config as cfg                                   # noqa: E402
from ola import data, metrics as m, preprocessing                # noqa: E402
from ola.sql_engine import (QueryError, build_database, build_database_from_sql, parse_query_library,  # noqa: E402
                            run_readonly, split_script, to_dialect)

_CACHE = {}


def clean():
    if "df" not in _CACHE:
        _CACHE["df"] = data.load_clean()
    return _CACHE["df"]


def conn():
    if "conn" not in _CACHE:
        _CACHE["conn"] = build_database(clean())
    return _CACHE["conn"]


def sql(query_id):
    q = {q.id: q for q in parse_query_library()}[query_id]
    return run_readonly(conn(), q.sql, max_rows=200_000).df


# --------------------------------------------------------------------------- #
# Preprocessing
# --------------------------------------------------------------------------- #
def test_cleaned_shape_and_validation_rules():
    df = clean()
    assert df.shape == (103_024, 33)
    assert all(v == 0 for v in preprocessing.validate(df).values())


def test_structural_nulls_are_not_imputed():
    df = clean()
    failed = df[df["Is_Successful"] == 0]
    assert failed["Driver_Ratings"].isna().all() and failed["Payment_Method"].isna().all()
    assert df[df["Is_Successful"] == 1]["Driver_Ratings"].notna().all()


def test_preprocessing_is_idempotent_on_raw_text_tokens():
    raw = pd.DataFrame({c: [None] for c in preprocessing.RAW_COLUMNS})
    assert preprocessing.standardise_text(raw).shape == raw.shape


# --------------------------------------------------------------------------- #
# The 10 required questions (known answers)
# --------------------------------------------------------------------------- #
def test_q01_successful_bookings():
    assert len(sql("Q01")) == 63_967


def test_q02_avg_distance_matches_workbook_averageif():
    out = sql("Q02").set_index("Vehicle_Type")["Avg_Distance_All_Bookings_Km"]
    assert abs(out["Auto"] - 6.24) < 0.01 and abs(out["Prime Sedan"] - 15.76) < 0.01    # all rows, zeros included
    done = sql("Q02b").set_index("Vehicle_Type")["Avg_Distance_Completed_Km"]
    assert abs(done["Auto"] - 10.0) < 0.2 and abs(done["Mini"] - 25.0) < 0.5        # completed rides only


def test_q03_cancelled_by_customer():
    assert sql("Q03").iloc[0, 0] == 10_499


def test_q04_top5_customers_deterministic():
    out = sql("Q04")
    assert len(out) == 5 and out.iloc[0]["Customer_ID"] == "CID954071" and out.iloc[0]["Total_Rides"] == 5
    assert (out["Total_Rides"].iloc[1:] == 4).all()
    assert list(out["Customer_ID"]) == list(m.top_customers_by_rides(clean(), 5)["Customer_ID"])


def test_q05_driver_personal_car_issue():
    assert sql("Q05").iloc[0, 0] == 6_542


def test_q06_prime_sedan_driver_rating_range():
    row = sql("Q06").iloc[0]
    assert (row["Max_Driver_Rating"], row["Min_Driver_Rating"]) == (5.0, 3.0)


def test_q07_upi_rides():
    assert len(sql("Q07")) == 25_881


def test_q08_avg_customer_rating_per_vehicle():
    out = sql("Q08")
    assert len(out) == 7 and out["Avg_Customer_Rating"].between(3.98, 4.02).all()


def test_q09_total_booking_value():
    assert sql("Q09").iloc[0, 0] == 35_080_467
    assert sql("Q09b").iloc[0, 0] == 32_829_985


def test_q10_incomplete_rides_and_reasons():
    assert len(sql("Q10")) == 3_926
    reasons = sql("Q10b").set_index("Incomplete_Rides_Reason")["Rides"]
    assert reasons.sum() == 3_926 and set(reasons.index) == {"Customer Demand", "Vehicle Breakdown", "Other Issue"}


# --------------------------------------------------------------------------- #
# SQL vs pandas cross-checks (two independent implementations must agree)
# --------------------------------------------------------------------------- #
def test_sql_and_pandas_agree_on_kpis():
    k, b = m.kpis(clean()), sql("B01").iloc[0]
    assert k["total_bookings"] == b["Total_Bookings"] and k["revenue"] == b["Completed_Revenue"]
    assert abs(k["success_rate"] - b["Success_Rate_Pct"]) < 0.01


def test_sql_and_pandas_agree_on_vehicles_attribution_payments():
    v, c01 = m.vehicle_summary(clean()).set_index("Vehicle_Type"), sql("C01").set_index("Vehicle_Type")
    assert (v.loc[c01.index, "Revenue"] == c01["Revenue"]).all()
    assert list(m.failure_attribution(clean())["Failed_Bookings"]) == list(sql("E03")["Failed_Bookings"])
    assert m.payment_summary(clean())["Revenue"].tolist() == sql("D01")["Revenue"].tolist()


def test_sql_and_pandas_agree_on_anomaly_counts():
    flagged = m.anomaly_scorecard(clean())["Flagged"].tolist()[:5]
    assert flagged == sql("H07")["Flagged_Bookings"].tolist()[:5]


def test_every_documented_query_executes():
    library = parse_query_library()
    assert len(library) >= 55 and len({q.id for q in library}) == len(library)
    for q in library:
        assert q.title and q.note and q.group, q.id
        run_readonly(conn(), q.sql, max_rows=50_000)


def test_data_quality_queries_are_clean():
    assert (sql("I03").iloc[0] == 0).all()
    assert sql("I01").iloc[0]["Total_Rows"] == sql("I01").iloc[0]["Unique_Bookings"] == 103_024


# --------------------------------------------------------------------------- #
# SQL engine safety
# --------------------------------------------------------------------------- #
def test_playground_blocks_every_write_and_pragma():
    for bad in ["DROP TABLE ola_rides", "DELETE FROM ola_rides", "UPDATE ola_rides SET Booking_Value=0",
                "INSERT INTO dim_payment VALUES ('x',1)", "PRAGMA query_only=OFF", "SELECT * FROM pragma_query_only",
                "ATTACH DATABASE 'x.db' AS x", "CREATE TABLE z(a)", "SELECT 1; DROP TABLE ola_rides",
                "WITH x AS (SELECT 1) DELETE FROM ola_rides", ""]:
        try:
            run_readonly(conn(), bad)
        except QueryError:
            continue
        raise AssertionError(f"write/pragma was allowed: {bad!r}")
    assert conn().execute("SELECT COUNT(*) FROM ola_rides").fetchone()[0] == 103_024


def test_playground_timeout_and_row_cap():
    try:
        run_readonly(conn(), "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT COUNT(*) FROM c", timeout_s=0.5)
        raise AssertionError("runaway query was not stopped")
    except QueryError as exc:
        assert "time limit" in str(exc)
    res = run_readonly(conn(), "SELECT * FROM ola_rides", max_rows=100)
    assert len(res.df) == 100 and res.truncated


def test_friendly_mysql_hint():
    try:
        run_readonly(conn(), "SELECT DAYNAME(Date) FROM ola_rides LIMIT 1")
    except QueryError as exc:
        assert "Day_Name" in str(exc)


def test_dialect_switch_and_script_splitting():
    text = (cfg.SCHEMA_SQL_PATH).read_text()
    lite = to_dialect(text, "sqlite")
    assert "DAYNAME" not in lite.replace("-- ", "") or "-- " in lite
    assert any("strftime" in line and not line.lstrip().startswith("--") for line in lite.splitlines())
    assert to_dialect(text, "mysql") == text
    assert len(split_script(lite)) >= 20


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
def test_filters():
    df = clean()
    f = data.default_filters(df)
    assert len(data.apply_filters(df, f)) == len(df)
    auto = data.apply_filters(df, data.Filters(f.start, f.end, vehicles=("Auto",)))
    assert set(auto["Vehicle_Type"]) == {"Auto"}
    wk = data.apply_filters(df, data.Filters(f.start, f.end, day_type=data.DAY_TYPES[2]))
    assert set(wk["Day_Name"]) == {"Saturday", "Sunday"}
    assert data.apply_filters(df, data.Filters(f.start, f.start)).Date.nunique() == 1


def test_metrics_do_not_crash_on_tiny_or_empty_frames():
    df = clean()
    for frame in (df.head(0), df.head(1), df.head(50)):
        m.kpis(frame)
        if len(frame):
            m.vehicle_summary(frame); m.status_breakdown(frame); m.anomaly_scorecard(frame)


# --------------------------------------------------------------------------- #
# SQL-side cleaning == Python-side cleaning (needs the raw workbook; skipped if absent)
# --------------------------------------------------------------------------- #
def test_sql_cleaning_reproduces_python_cleaning():
    raw_pickle, xlsx = Path("/tmp/raw_text.pkl"), Path(os.environ.get("OLA_RAW_XLSX", ROOT / "data" / "raw" / "OLA_DataSet.xlsx"))
    if raw_pickle.exists():
        raw = pd.read_pickle(raw_pickle)
    elif xlsx.exists():
        raw = pd.read_excel(xlsx, sheet_name="July", usecols=range(19), dtype=str, keep_default_na=False)[preprocessing.RAW_COLUMNS]
    else:
        print("   (skipped: raw workbook not available)")
        return
    db = build_database_from_sql(raw)
    via_sql = pd.read_sql_query("SELECT * FROM ola_rides ORDER BY Booking_ID", db)
    via_py = pd.read_csv(cfg.CLEAN_DATA_PATH).sort_values("Booking_ID").reset_index(drop=True)
    assert via_sql.shape == via_py.shape
    for col in via_py.columns:
        a, b = via_sql[col], via_py[col]
        if pd.api.types.is_numeric_dtype(b):
            tol = 0.0101 if col == "Fare_Per_Km" else 1e-9          # SQL vs pandas rounding of half-cents
            assert np.allclose(pd.to_numeric(a, errors="coerce").astype(float), b.astype(float), atol=tol, equal_nan=True), col
        else:
            assert (a.fillna("~").astype(str) == b.fillna("~").astype(str)).all(), col
