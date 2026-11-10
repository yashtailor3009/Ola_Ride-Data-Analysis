"""
ola.context
===========
A small container passed to every Streamlit view so views never reach for globals.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import pandas as pd

from .data import Filters
from .metrics import Insight
from .sql_engine import QueryDef


@dataclass
class AppContext:
    df: pd.DataFrame                 # rows after the sidebar filters
    full: pd.DataFrame               # the complete cleaned dataset
    filters: Filters
    conn: sqlite3.Connection         # locked-down in-memory SQLite (playground)
    queries: list[QueryDef]
    insights: list[Insight]
    dq_report: dict = field(default_factory=dict)
    powerbi_url: str = ""
    scope: str = ""                  # human-readable description of the active filters
