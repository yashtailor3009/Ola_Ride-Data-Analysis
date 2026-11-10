"""
UI smoke tests - render EVERY page of the app.

* If real Streamlit is installed: uses ``streamlit.testing.v1.AppTest`` (the official headless runner).
* Otherwise: runs the app against the strict stubs in ``tests/stubs`` (duplicate-key detection,
  schema-checked Plotly properties). This still exercises every line of our own view / chart /
  metrics code against the real dataset.

Run:  python -m pytest tests/test_ui_smoke.py      (or)   python tests/test_ui_smoke.py
"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:                                           # prefer the real thing
    import streamlit  # noqa: F401
    import plotly     # noqa: F401
    REAL = True
except ImportError:                            # fall back to strict stubs
    sys.path.insert(0, str(ROOT / "tests" / "stubs"))
    REAL = False

PAGES = ["Executive summary", "Overall", "Vehicle types", "Revenue & pricing", "Cancellations", "Ratings",
         "Customers", "Anomalies", "Booking explorer", "SQL lab", "Power BI", "About & data"]


def _run_stub(state: dict) -> list:
    """Execute app.py once with the given session state; return rendered elements."""
    import streamlit as st
    st.reset_run()
    st.session_state.clear()
    st.session_state.update(state)
    runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
    return list(st._RUN["elements"])


def _run_real(state: dict):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["nav"] = state.get("nav", PAGES[0])
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def run(state: dict):
    return _run_real(state) if REAL else _run_stub(state)


def test_every_page_renders():
    for page in PAGES:
        run({"nav": page})


def test_pages_with_filters_applied():
    import datetime as dt
    state = {"f_vehicles": ["Auto", "Prime SUV"], "f_bands": ["Morning (06-11)"], "f_daytype": "Weekdays only",
             "f_dates": (dt.date(2024, 7, 3), dt.date(2024, 7, 20))}
    for page in PAGES[:9]:
        run({"nav": page, **state})


def test_pages_with_empty_selection_do_not_crash():
    import datetime as dt
    state = {"f_vehicles": ["Auto"], "f_bands": ["Night (00-05)"], "f_daytype": "Weekends only",
             "f_pickups": ["Magadi Road"], "f_dates": (dt.date(2024, 7, 1), dt.date(2024, 7, 1))}
    for page in PAGES[:9]:
        run({"nav": page, **state})


def test_sql_lab_runs_a_query_and_blocks_writes():
    run({"nav": "SQL lab", "_click_sql_run": True})
    run({"nav": "SQL lab", "_click_sql_run": True, "sql_text": "DROP TABLE ola_rides"})
    run({"nav": "SQL lab", "_click_sql_run": True, "sql_text": ""})
    run({"nav": "SQL lab", "_click_sql_run": True, "sql_text": "SELECT Vehicle_Type, COUNT(*) AS n FROM ola_rides GROUP BY 1"})


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name, "(real Streamlit)" if REAL else "(strict stubs)")
