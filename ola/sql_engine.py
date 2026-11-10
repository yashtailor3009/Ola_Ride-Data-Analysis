"""
ola.sql_engine
==============
Everything the project needs to *run SQL*:

* ``to_dialect``           flips the MySQL/SQLite tagged lines in the .sql files
* ``parse_query_library``  reads ``sql/ola_queries.sql`` into structured ``QueryDef`` objects
* ``build_database``       creates the in-memory SQLite database the app queries
* ``run_readonly``         executes user SQL safely (SELECT only, row cap, timeout)
* ``schema_info``          table/column catalogue for the playground's schema browser

Why SQLite for the live playground?
It ships with Python (no server to host), and the project's queries are written
in the portable subset shared with MySQL 8, so the same text runs on both.

Safety model of ``run_readonly`` (defence in depth - a visitor can type anything):
1. SQLite *authorizer* callback whitelists only SELECT / READ / FUNCTION actions,
   so INSERT, DROP, ATTACH, PRAGMA, ... are rejected by the engine itself.
2. ``PRAGMA query_only = ON`` as a second guard against writes.
3. A progress-handler deadline aborts runaway queries (default 10 s).
4. At most ``max_rows`` rows are fetched, so a huge SELECT cannot exhaust memory.
"""
from __future__ import annotations

import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config as cfg

# SQLite authorizer action codes we allow (numeric so we do not depend on the
# Python version exposing the sqlite3.SQLITE_* constants).
_SQLITE_SELECT, _SQLITE_READ, _SQLITE_FUNCTION, _SQLITE_RECURSIVE, _SQLITE_PRAGMA = 21, 20, 31, 33, 19
_ALLOWED_ACTIONS = {_SQLITE_SELECT, _SQLITE_READ, _SQLITE_FUNCTION, _SQLITE_RECURSIVE}
# The only PRAGMAs permitted: read-only schema introspection (used by the Schema tab).
_ALLOWED_PRAGMAS = {"table_info", "table_xinfo"}
_SQLITE_OK, _SQLITE_DENY = 0, 1

# The Streamlit app shares one in-memory connection across sessions; serialise access to it.
_RUN_LOCK = threading.Lock()


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #
@dataclass
class QueryDef:
    """One documented query from ``ola_queries.sql``."""
    id: str
    group: str
    title: str
    note: str
    sql: str


@dataclass
class QueryResult:
    """Outcome of a successful playground query."""
    df: pd.DataFrame
    elapsed_ms: float
    truncated: bool = False
    max_rows: int = 0
    notes: list[str] = field(default_factory=list)


class QueryError(Exception):
    """Raised with a *user-friendly* message when a query cannot be run."""


# --------------------------------------------------------------------------- #
# Dialect handling
# --------------------------------------------------------------------------- #
def to_dialect(sql: str, dialect: str = "sqlite") -> str:
    """Return ``sql`` with the dialect-tagged line pairs switched.

    Convention in the .sql files:
        ``<code>  -- [MySQL]``       active by default
        ``-- [SQLite] <code>``       commented by default
    ``dialect='mysql'`` returns the text unchanged.
    """
    if dialect.lower() == "mysql":
        return sql
    if dialect.lower() != "sqlite":
        raise ValueError("dialect must be 'mysql' or 'sqlite'")
    out = []
    for line in sql.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("-- [SQLite]"):
            out.append(line.replace("-- [SQLite]", "", 1))
        elif line.rstrip().endswith("-- [MySQL]"):
            out.append("-- " + line)           # comment the MySQL-only line out
        else:
            out.append(line)
    return "\n".join(out)


def _strip_comments(statement: str) -> str:
    """Remove whole-line ``--`` comments so a statement's first keyword can be inspected."""
    return "\n".join(l for l in statement.splitlines() if not l.strip().startswith("--")).strip()


def split_script(sql: str) -> list[str]:
    """Split a SQL script into complete statements.

    Uses ``sqlite3.complete_statement`` so semicolons inside comments or string
    literals never cause a false split. Comment-only fragments are dropped.
    """
    statements, buffer = [], ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            if _strip_comments(buffer):
                statements.append(buffer.strip())
            buffer = ""
    return statements


# --------------------------------------------------------------------------- #
# Query library
# --------------------------------------------------------------------------- #
_TAG = re.compile(r"^--\s*@(\w+):\s*(.*)$")


def parse_query_library(path: Path = cfg.QUERIES_SQL_PATH) -> list[QueryDef]:
    """Parse ``ola_queries.sql`` into a list of ``QueryDef``.

    A block starts at a ``-- @id:`` line and runs to the next ``-- @id:`` (or the
    end of the file). ``@group``/``@title``/``@note`` lines are metadata; the
    remaining non-banner lines form the SQL text.
    """
    blocks, current = [], None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        match = _TAG.match(raw.strip())
        if match and match.group(1) == "id":
            current = {"id": match.group(2).strip(), "group": "", "title": "", "note": "", "sql": []}
            blocks.append(current)
        elif current is None:
            continue
        elif match:
            key, value = match.group(1), match.group(2).strip()
            if key in ("group", "title"):
                current[key] = value
            elif key == "note":
                current["note"] = (current["note"] + " " + value).strip()
        else:
            current["sql"].append(raw)

    library = []
    for b in blocks:
        # Keep everything up to the last ';' - drops the section-banner comments
        # that sit between one query and the next @id tag.
        text = "\n".join(b["sql"]).strip()
        end = text.rfind(";")
        sql_text = (text[: end + 1] if end != -1 else text).strip()
        library.append(QueryDef(b["id"], b["group"], b["title"], b["note"], sql_text))
    return library


# --------------------------------------------------------------------------- #
# Database construction
# --------------------------------------------------------------------------- #
def _dimension_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build dim_vehicle / dim_payment from config (mirrors the INSERTs in the schema file)."""
    dim_vehicle = pd.DataFrame({
        "Vehicle_Type": list(cfg.VEHICLE_CLASS),
        "Vehicle_Class": list(cfg.VEHICLE_CLASS.values()),
    })
    dim_vehicle["Has_AC"] = (~dim_vehicle["Vehicle_Type"].isin(cfg.NON_AC_VEHICLES)).astype(int)
    dim_vehicle["Icon_URL"] = dim_vehicle["Vehicle_Type"].map(cfg.VEHICLE_ICONS)
    dim_payment = pd.DataFrame({
        "Payment_Method": ["Cash", "UPI", "Credit Card", "Debit Card"],
        "Is_Digital": [0, 1, 1, 1],
    })
    return dim_vehicle, dim_payment


_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_rides_status   ON ola_rides (Booking_Status)",
    "CREATE INDEX IF NOT EXISTS idx_rides_vehicle  ON ola_rides (Vehicle_Type)",
    "CREATE INDEX IF NOT EXISTS idx_rides_customer ON ola_rides (Customer_ID)",
    "CREATE INDEX IF NOT EXISTS idx_rides_date     ON ola_rides (Date)",
    "CREATE INDEX IF NOT EXISTS idx_rides_payment  ON ola_rides (Payment_Method)",
]


def _lock_down(conn: sqlite3.Connection) -> None:
    """Install the authorizer + query_only guard (see module docstring)."""
    def authorizer(action, arg1, *_rest):
        if action in _ALLOWED_ACTIONS:
            return _SQLITE_OK
        if action == _SQLITE_PRAGMA and str(arg1).lower() in _ALLOWED_PRAGMAS:
            return _SQLITE_OK
        return _SQLITE_DENY

    conn.execute("PRAGMA query_only = ON")
    conn.set_authorizer(authorizer)


def build_database(clean: pd.DataFrame, lock: bool = True) -> sqlite3.Connection:
    """Create an in-memory SQLite DB from the cleaned frame.

    Tables: ``ola_rides`` (fact), ``dim_vehicle``, ``dim_payment``.
    Dates are stored as ISO text (``YYYY-MM-DD``) which sorts and compares
    correctly in both SQLite and MySQL.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    frame = clean.copy()
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.strftime("%Y-%m-%d")
    frame["Booking_Datetime"] = pd.to_datetime(frame["Booking_Datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    frame.to_sql("ola_rides", conn, index=False, if_exists="replace")
    dim_vehicle, dim_payment = _dimension_frames()
    dim_vehicle.to_sql("dim_vehicle", conn, index=False, if_exists="replace")
    dim_payment.to_sql("dim_payment", conn, index=False, if_exists="replace")
    for stmt in _INDEXES:
        conn.execute(stmt)
    conn.execute("CREATE VIEW v_successful_bookings AS SELECT * FROM ola_rides WHERE Booking_Status = 'Success'")
    conn.execute("CREATE VIEW v_failed_bookings AS SELECT * FROM ola_rides WHERE Booking_Status <> 'Success'")
    conn.commit()
    if lock:
        _lock_down(conn)
    return conn


def build_database_from_sql(raw_text: pd.DataFrame, schema_path: Path = cfg.SCHEMA_SQL_PATH) -> sqlite3.Connection:
    """Rebuild the database by running the *SQL-side* cleaning pipeline.

    ``raw_text`` must be the workbook exactly as exported (all values as text,
    missing values as the literal string ``'null'``). Used by the test-suite to
    prove the SQL cleaning produces the same table as the Python pipeline.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    script = to_dialect(Path(schema_path).read_text(encoding="utf-8"), "sqlite")
    statements = split_script(script)
    # Run everything up to (and including) the staging table, load the data,
    # then run the rest (view -> typed table -> dimensions -> indexes).
    for stmt in statements:
        conn.execute(stmt)
        if _strip_comments(stmt).upper().startswith("CREATE TABLE IF NOT EXISTS RIDES_RAW"):
            raw_text.to_sql("rides_raw", conn, index=False, if_exists="append")
    conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# Safe execution
# --------------------------------------------------------------------------- #
_MYSQL_HINTS = {
    r"\bDATE_FORMAT\s*\(": "DATE_FORMAT() is MySQL-only. In SQLite use strftime('%Y-%m-%d', col). "
                           "Tip: the table already has Date, Ride_Hour, Day_Name and Time_Band columns.",
    r"\bDAYNAME\s*\(": "DAYNAME() is MySQL-only - use the ready-made Day_Name column.",
    r"\bHOUR\s*\(": "HOUR() is MySQL-only - use the ready-made Ride_Hour column.",
    r"\bNOW\s*\(|\bCURDATE\s*\(": "NOW()/CURDATE() are not available; the data is a fixed snapshot (July 2024).",
    r"\bCONCAT\s*\(": "CONCAT() is not available in older SQLite - use the || operator instead.",
    r"\bSTDDEV|\bVARIANCE|\bMEDIAN\s*\(|\bPERCENTILE": "This engine has no STDDEV/MEDIAN/PERCENTILE - use NTILE() or window functions.",
    r"`": "Backticks are MySQL quoting - use plain identifiers or double quotes.",
}


def _friendly_error(sql: str, exc: Exception) -> str:
    """Translate a raw sqlite3 error into advice a learner can act on."""
    message = str(exc)
    hints = [h for pattern, h in _MYSQL_HINTS.items() if re.search(pattern, sql, flags=re.I)]
    if "not authorized" in message or "authoriz" in message.lower():
        return "Only read-only SELECT queries are allowed in the playground (no INSERT, UPDATE, DELETE, DROP, PRAGMA, ATTACH)."
    if "interrupted" in message.lower():
        return "The query ran longer than the time limit and was stopped. Add a WHERE filter or a LIMIT."
    if "no such table" in message:
        return f"{message}. Available tables: ola_rides, dim_vehicle, dim_payment (see the Schema tab)."
    if "no such column" in message:
        return f"{message}. Open the Schema tab for the exact column names."
    if "only execute one statement" in message.lower():
        return "Run one statement at a time (remove extra semicolon-separated queries)."
    return message + ("  Hint: " + " ".join(hints) if hints else "")


def run_readonly(conn: sqlite3.Connection, sql: str, max_rows: int = 5000,
                 timeout_s: float = 10.0) -> QueryResult:
    """Execute ``sql`` safely and return a DataFrame.

    Raises
    ------
    QueryError
        With a human-readable message for empty input, non-SELECT statements,
        engine errors, authorizer rejections and timeouts.
    """
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        raise QueryError("Type a query first - for example: SELECT * FROM ola_rides LIMIT 10")
    first_word = re.sub(r"^(\s*--[^\n]*\n|\s*/\*.*?\*/)*\s*", "", text, flags=re.S).split(None, 1)
    if not first_word or first_word[0].upper() not in {"SELECT", "WITH", "EXPLAIN", "VALUES"}:
        raise QueryError("Only SELECT / WITH queries are allowed in the playground.")

    deadline = time.monotonic() + timeout_s
    started = time.perf_counter()
    with _RUN_LOCK:
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 20_000)
        try:
            cursor = conn.execute(text)
            if cursor.description is None:
                raise QueryError("That statement does not return rows. Use a SELECT query.")
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchmany(max_rows + 1)
        except QueryError:
            raise
        except sqlite3.Error as exc:                   # engine-level error -> friendly text
            raise QueryError(_friendly_error(text, exc)) from exc
        finally:
            conn.set_progress_handler(None, 0)

    truncated = len(rows) > max_rows
    frame = pd.DataFrame(rows[:max_rows], columns=columns)
    elapsed = (time.perf_counter() - started) * 1000
    return QueryResult(frame, elapsed, truncated, max_rows)


def query_df(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> pd.DataFrame:
    """Small internal helper: run a trusted SELECT and return a DataFrame."""
    return pd.read_sql_query(sql, conn, params=params)


def schema_info(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return ``Object | Kind | Column | Type`` for every table and view.

    Uses the table-valued ``pragma_table_info()`` function. The authorizer
    whitelists exactly this read-only pragma; every other PRAGMA stays blocked.
    """
    objects = conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
        "AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    rows = []
    for name, kind in objects:
        for _cid, col, col_type, *_ in conn.execute("SELECT * FROM pragma_table_info(?)", (name,)):
            rows.append({"Object": name, "Kind": kind, "Column": col, "Type": col_type})
    return pd.DataFrame(rows)
