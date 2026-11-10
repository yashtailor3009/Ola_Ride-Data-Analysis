# Ola Ride Insights

End-to-end analytics project on **103,024 Ola bookings (July 2024)**: data cleaning, SQL analysis, a Power BI build kit,
an interactive **Streamlit** dashboard with a **live SQL playground**, a PDF insights report and a slide deck.

> **Headline finding:** only **62.1%** of bookings become a ride. The failure rate is identical across every vehicle type, hour,
> weekday and pickup area, so the cause is systemic (dispatch and driver supply). About **88%** of failures trace back to the
> supply side, and every 10% of failed bookings recovered is worth roughly **₹2.15 M** (+6.1% revenue).

## What is in the box

| Deliverable | Where | Notes |
|---|---|---|
| Data preprocessing | `ola/preprocessing.py`, `data/ola_rides_clean.csv.gz`, `data/data_quality_report.json` | 15 validation rules, 14 derived features, nulls kept (they are structural) |
| SQL analysis | `sql/ola_schema_and_cleaning.sql`, `sql/ola_queries.sql` | 58 documented queries incl. all 10 required; MySQL 8 + SQLite |
| Streamlit app | `app.py`, `ola/` | 12 views, global filters, booking search, SQL playground |
| Power BI kit | `powerbi/` | Theme, 35 DAX measures, Power Query, build guide (a `.pbix` can only be authored in Power BI Desktop) |
| PDF report | `reports/OLA_Ride_Insights_Report.pdf` | 18 pages: findings, reasons, recommendations, SQL appendix |
| Presentation | `reports/OLA_Ride_Insights_Presentation.pptx` | 15 slides, native charts, speaker notes |
| Logo | `assets/` | Original mark + lock-ups (PNG, SVG) |
| EDA notebook | `notebooks/01_EDA.ipynb` | Matplotlib/Seaborn exploration |
| Tests | `tests/` | Known SQL answers, SQL-vs-pandas cross-checks, engine safety, UI smoke tests |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The cleaned dataset is already in `data/`, so the app starts immediately. To rebuild it from the original workbook:

```bash
python -m ola.preprocessing --raw path/to/OLA_DataSet.xlsx     # reads sheet "July", writes data/*.csv.gz + report
```

Other commands:

```bash
python tests/run_all.py                    # all tests (no pytest needed);  python -m pytest -q  also works
python scripts/build_assets.py             # regenerate the logo files
python scripts/report_charts.py            # regenerate PDF charts
python scripts/build_pdf.py                # rebuild the PDF report (needs reportlab, matplotlib)
python scripts/export_deck_data.py && node scripts/build_pptx.js     # rebuild the slide deck (needs pptxgenjs)
python scripts/make_notebook.py            # regenerate the EDA notebook
```

## Project structure

```
app.py                       Streamlit entry: sidebar (nav + filters) -> AppContext -> view
ola/
  config.py                  paths, brand palette, thresholds, vehicle metadata (single source of constants)
  preprocessing.py           load -> standardise -> convert types -> derive features -> validate -> report
  data.py                    load cleaned data, Filters dataclass, apply_filters
  metrics.py                 ALL numbers: KPIs, tables, anomaly rules, statistical tests, insight cards, roadmap
  sql_engine.py              dialect switch, query-library parser, DB builder, hardened read-only runner
  charts.py                  Plotly figure builders (labels + one computed annotation per chart)
  theme.py                   CSS, KPI/insight cards, chart blocks, Streamlit-version-safe wrappers
  views/                     one module per page: summary, overall, vehicles, revenue, cancellations,
                             ratings, customers, anomalies, explorer, sql_lab, powerbi, about
sql/                         schema + cleaning (MySQL/SQLite) and the analysis queries
powerbi/                     OLA_Theme.json, measures.dax, power_query.m, BUILD_GUIDE.md
scripts/                     logo, report charts, PDF, deck, notebook generators
tests/                       unit + smoke tests (tests/stubs = strict Streamlit/Plotly stand-ins)
```

**Design principle - one source of truth.** Every number shown anywhere comes from `ola/metrics.py` (or from running the SQL file),
so the app, PDF and slides cannot disagree. Pure logic (`metrics`, `data`, `sql_engine`, `preprocessing`) has no Streamlit
dependency and is unit-tested; the UI layers (`charts`, `theme`, `views`) are thin.

## SQL

* `ola_schema_and_cleaning.sql` builds the model: `rides_raw` (staging, all text) → `v_rides_clean` (NULLIF/TRIM/CAST) →
  `ola_rides` (typed table + derived columns) plus `dim_vehicle`, `dim_payment`, indexes and views.
* `ola_queries.sql` holds 58 queries in nine groups: **A** the 10 required questions, **B** overall & demand, **C** vehicles,
  **D** revenue & pricing, **E** cancellations, **F** ratings, **G** customers, **H** anomalies & fraud, **I** data quality.
  Each carries `@id / @group / @title / @note` tags that the app reads, so the playground always shows the file's own text.
* **MySQL:** run the schema file, load your CSV export into `rides_raw` (`LOAD DATA LOCAL INFILE`, see comments), then run any query.
  **SQLite:** `to_dialect()` flips the few tagged lines (`DAYNAME`/`WEEKDAY`); queries themselves are portable.
* Workbook-faithful answers: Q02 averages distance over *all* bookings (matches the workbook's `AVERAGEIF`); Q02b gives the
  business-correct completed-only figure. Q09 uses `Booking_Status = 'Success'`; Q09b excludes rides flagged incomplete.
  Q04's top-5 has ties (26 customers share 4 bookings), broken by completed value then ID so the answer is deterministic.

## Streamlit app

Sidebar navigation + global filters (date range, vehicle, time of day, weekday/weekend, pickup area) feed every analytic page.
Each chart has an action headline, labelled axes, a computed annotation and a "so what". The **SQL lab** runs read-only SQL
(authorizer whitelist, `query_only`, 10 s timeout, 5,000-row cap), with an example library, schema browser, MySQL→SQLite
cheat-sheet, history, CSV download and one-click charting.

**Embed Power BI (optional):** publish your report, then set `POWERBI_EMBED_URL` in `.streamlit/secrets.toml`
(see `secrets.toml.example`) or as an environment variable.

**Deploy free on Streamlit Community Cloud:** push this folder to GitHub → *New app* → pick the repo and `app.py` → (optionally)
add `POWERBI_EMBED_URL` under *Secrets*. The repository already contains the cleaned data.

## Power BI

`powerbi/BUILD_GUIDE.md` is a page-by-page recipe for the five views and ten visuals in the brief, with theme, DAX (expected values
in comments for verification), Power Query for the cleaned CSV or the original workbook, interactivity checklist and publishing steps.

## Data decisions and assumptions

* **Nulls are structural, not missing** (ratings/payment/TAT exist only for completed rides; reasons only for their status) → never imputed.
* **Revenue = Booking_Value of completed rides.** On failed bookings Booking_Value is a *quote*; the sum is reported as "quoted fare lost".
* **Time bands** are four equal 6-hour windows so bands are comparable. **Vehicle class** (two-wheeler / three-wheeler / cab) and **Has_AC**
  are analyst assumptions used for JOIN examples and the AC-anomaly rule.
* `V_TAT` / `C_TAT` units are not documented in the source; they are used as relative measures only.
* The dataset covers one month, so trends and retention over time cannot be measured.
* Hours, weekdays, locations, ratings and fares are unusually uniform - typical of a sampled/synthetic extract. Findings about
  uniformity and attribution are robust *within* the data; re-run the pipeline on production data before operational decisions.

## Testing

`python tests/run_all.py` runs 29 checks: the ten required SQL answers against known values, SQL-vs-pandas agreement
(KPIs, vehicle scorecard, attribution, top customers, payments, anomalies), SQL-side cleaning vs Python cleaning on all 103,024 rows
(needs the raw workbook at `data/raw/OLA_DataSet.xlsx` or `OLA_RAW_XLSX=...`; skipped otherwise), playground security (every write/PRAGMA blocked, timeout, row cap), filters,
and a smoke test that renders every page. With Streamlit installed the smoke test uses the official `AppTest`; without it, it uses
the strict stand-ins in `tests/stubs`, which reject duplicate widget keys and misspelled Plotly properties.

## Troubleshooting

| Problem | Fix |
|---|---|
| `FileNotFoundError ... ola_rides_clean.csv.gz` | Run `python -m ola.preprocessing --raw OLA_DataSet.xlsx` |
| Fonts look different offline | Fonts load from Google Fonts with system fallbacks; layout is unaffected |
| Vehicle icons are blank in the scorecard | Icons are remote URLs (from the workbook's lookup sheet); they need internet access |
| Streamlit shows deprecation warnings | `ola/theme.py` picks `width="stretch"` vs `use_container_width` by version; keep `streamlit>=1.50` |
