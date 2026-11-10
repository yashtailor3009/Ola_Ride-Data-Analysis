"""About & Data - data dictionary, cleaning log, caveats, and how to run the project."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..context import AppContext
from ..dictionary import DATA_DICTIONARY
from .. import theme as ui


def render(ctx: AppContext) -> None:
    ui.page_header("About the data & project", "Provenance, cleaning decisions, caveats and how everything fits together.",
                   scope="Documentation")
    rep = ctx.dq_report
    if rep:
        c = st.columns(4)
        c[0].markdown(ui.kpi_card("Rows (raw → clean)", f"{rep['rows_raw']:,} → {rep['rows_clean']:,}", "no rows dropped"), unsafe_allow_html=True)
        c[1].markdown(ui.kpi_card("Columns (raw → clean)", f"{rep['columns_raw']} → {rep['columns_clean']}", "14 derived columns"), unsafe_allow_html=True)
        c[2].markdown(ui.kpi_card("Validation rules", f"{len(rep['validation_rules_violations'])}",
                                  "all passing" if rep["all_rules_pass"] else "violations found"), unsafe_allow_html=True)
        c[3].markdown(ui.kpi_card("Date range", f"{rep['date_range'][0][5:]} → {rep['date_range'][1][5:]}", "July 2024"), unsafe_allow_html=True)

        ui.section("Cleaning decisions")
        for d in rep["cleaning_decisions"]:
            st.markdown(f"- {d}")
        ui.section("Caveats you should know")
        for d in rep["caveats"]:
            st.markdown(f"- {d}")
        with st.expander("Validation rules (violations should all be 0)"):
            ui.show_table(pd.DataFrame(rep["validation_rules_violations"].items(), columns=["Rule", "Violations"]))
        with st.expander("Structural nulls (expected - not errors)"):
            ui.show_table(pd.DataFrame(rep["structural_nulls"].items(), columns=["Column", "Null count"]))

    ui.section("Data dictionary")
    ui.show_table(pd.DataFrame(DATA_DICTIONARY, columns=["Column", "Type", "Origin", "Meaning"]))

    ui.section("Project map")
    st.markdown(
        "- `ola/preprocessing.py` - cleaning pipeline (run once to produce the cleaned data)\n"
        "- `sql/ola_schema_and_cleaning.sql` and `sql/ola_queries.sql` - the SQL deliverable (MySQL 8 / SQLite)\n"
        "- `ola/metrics.py` - every number and insight, as testable pandas functions\n"
        "- `ola/charts.py`, `ola/theme.py`, `ola/views/` - the dashboard UI\n"
        "- `powerbi/` - Power BI theme, DAX, Power Query and build guide\n"
        "- `tests/` - unit tests including SQL-vs-pandas cross-checks")
