"""
SQL Lab - a live, read-only SQL playground on the project's own data.

Tabs
----
* Playground  : pick a documented query (or write your own), run it, chart it, download it.
* Query library: every query from ``sql/ola_queries.sql`` with its business note.
* Schema       : tables, columns, sample rows and a MySQL -> SQLite cheat-sheet.

Safety: execution goes through ``ola.sql_engine.run_readonly`` (authorizer, row cap, timeout).
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from .. import charts
from ..context import AppContext
from ..sql_engine import QueryError, run_readonly, schema_info
from .. import theme as ui

MAX_ROWS = 5000
CHEATSHEET = pd.DataFrame([
    ("DAYNAME(Date)", "Day_Name  (ready-made column)"),
    ("HOUR(Time)", "Ride_Hour  (ready-made column)"),
    ("DATE_FORMAT(Date, '%Y-%m')", "strftime('%Y-%m', Date)"),
    ("CONCAT(a, b)", "a || b"),
    ("IF(cond, x, y)", "CASE WHEN cond THEN x ELSE y END"),
    ("STDDEV(x)", "not available - use AVG and window functions"),
    ("LIMIT 10 OFFSET 5", "same"),
    ("RANK() / NTILE() / SUM() OVER (...)", "same (window functions are supported)"),
], columns=["MySQL", "This playground (SQLite)"])


def _load_selected_query(by_id: dict) -> None:
    """Callback: copy the chosen example into the editor."""
    st.session_state["sql_text"] = by_id[st.session_state["sql_pick"]].sql


def _on_topic_change(by_id: dict, ids_by_group: dict) -> None:
    """Callback: switching topic selects that topic's first query and loads it."""
    first = ids_by_group[st.session_state["sql_group"]][0]
    st.session_state["sql_pick"] = first
    st.session_state["sql_text"] = by_id[first].sql


def _load_history() -> None:
    st.session_state["sql_text"] = st.session_state["sql_hist_pick"]


def render(ctx: AppContext) -> None:
    ui.page_header("SQL lab", "Run real SQL against the cleaned ride data. Read-only: only SELECT / WITH queries are allowed.",
                   scope="Live · SQLite engine · full July dataset")
    by_id = {q.id: q for q in ctx.queries}
    groups = list(dict.fromkeys(q.group for q in ctx.queries))
    ids_by_group = {g: [q.id for q in ctx.queries if q.group == g] for g in groups}
    st.session_state.setdefault("sql_text", ctx.queries[0].sql)
    st.session_state.setdefault("sql_history", [])

    tab_play, tab_lib, tab_schema = st.tabs(["Playground", "Query library", "Schema & cheat-sheet"])

    # ------------------------------------------------------------------ #
    with tab_play:
        c1, c2 = st.columns([1, 2])
        group = c1.selectbox("Topic", groups, key="sql_group", on_change=_on_topic_change, args=(by_id, ids_by_group))
        ids = ids_by_group[group]
        c2.selectbox("Example query", ids, key="sql_pick", format_func=lambda i: f"{i} · {by_id[i].title}",
                     on_change=_load_selected_query, args=(by_id,))
        picked = by_id.get(st.session_state.get("sql_pick", ids[0]), by_id[ids[0]])
        ui.callout(f"<b>{html.escape(picked.id)} - what it tells us:</b> {html.escape(picked.note)}", "info")

        sql = st.text_area("SQL editor", key="sql_text", height=260,
                           help="Tables: ola_rides, dim_vehicle, dim_payment (and views v_successful_bookings, v_failed_bookings).")
        run_col, _, hist_col = st.columns([1, 1, 3])
        run = run_col.button("Run query", type="primary", key="sql_run")
        if st.session_state["sql_history"]:
            hist_col.selectbox("Recent queries", [h for h in st.session_state["sql_history"]], key="sql_hist_pick",
                               format_func=lambda s: " ".join(s.split())[:90], on_change=_load_history, label_visibility="collapsed")

        if run:
            try:
                result = run_readonly(ctx.conn, sql, max_rows=MAX_ROWS)
            except QueryError as exc:
                st.error(str(exc))
            else:
                hist = [h for h in st.session_state["sql_history"] if h != sql]
                st.session_state["sql_history"] = ([sql] + hist)[:8]
                st.session_state["sql_result"] = result.df
                st.session_state["sql_meta"] = (len(result.df), result.elapsed_ms, result.truncated)

        frame = st.session_state.get("sql_result")
        if frame is not None:
            rows, ms, truncated = st.session_state["sql_meta"]
            st.caption(f"{rows:,} rows · {ms:,.0f} ms" + (f" · result capped at {MAX_ROWS:,} rows" if truncated else ""))
            ui.show_table(frame)
            st.download_button("Download result (CSV)", frame.to_csv(index=False).encode("utf-8"), "query_result.csv", "text/csv", key="sql_dl")
            numeric = [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
            labels = [c for c in frame.columns if c not in numeric] or list(frame.columns)
            if numeric and len(frame) > 1:
                with st.expander("Chart this result"):
                    x = st.selectbox("Category (x)", labels, key="sql_x")
                    y = st.selectbox("Value (y)", numeric, key="sql_y")
                    ui.show_plot(charts.quick_bar(frame, x, y), key="sql_chart")

    # ------------------------------------------------------------------ #
    with tab_lib:
        st.caption(f"{len(ctx.queries)} documented queries from sql/ola_queries.sql. Use the Playground tab to run them.")
        for g in groups:
            with st.expander(g, expanded=g.startswith("A.")):
                for q in [q for q in ctx.queries if q.group == g]:
                    st.markdown(f"**{q.id} · {q.title}**")
                    st.caption(q.note)
                    st.code(q.sql, language="sql")

    # ------------------------------------------------------------------ #
    with tab_schema:
        info = schema_info(ctx.conn)
        names = list(dict.fromkeys(info["Object"]))
        pick = st.selectbox("Table or view", names, key="sql_schema_pick")
        ui.show_table(info[info["Object"] == pick][["Column", "Type"]])
        try:
            sample = run_readonly(ctx.conn, f'SELECT * FROM "{pick}" LIMIT 5').df
            st.markdown("**Sample rows**")
            ui.show_table(sample)
        except QueryError as exc:
            st.caption(str(exc))
        st.markdown("**Writing MySQL? Translate these**")
        ui.show_table(CHEATSHEET)
