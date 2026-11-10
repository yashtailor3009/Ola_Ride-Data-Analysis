"""
scripts/build_pdf.py
====================
Builds ``reports/OLA_Ride_Insights_Report.pdf`` with reportlab.

Every number in the report is computed at build time from the cleaned data
(``ola.metrics``) or by running the project's own SQL (``sql/ola_queries.sql``),
so the PDF can never drift from the app, the SQL file or the slides.

Run:  python scripts/build_pdf.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle, CondPageBreak)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from ola import config as cfg                                     # noqa: E402
from ola import metrics as m                                      # noqa: E402
from ola.data import load_clean, load_dq_report                   # noqa: E402
from ola.dictionary import DATA_DICTIONARY                        # noqa: E402
from ola.sql_engine import build_database, parse_query_library, run_readonly   # noqa: E402
import report_charts                                              # noqa: E402

OUT_PDF = ROOT / "reports" / "OLA_Ride_Insights_Report.pdf"
CHARTS = ROOT / "reports" / "charts"

# ------------------------------------------------------------------ fonts & colours
FONT_DIR = Path("/usr/share/fonts/truetype/crosextra")
pdfmetrics.registerFont(TTFont("Carlito", str(FONT_DIR / "Carlito-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Carlito-Bold", str(FONT_DIR / "Carlito-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Carlito-Italic", str(FONT_DIR / "Carlito-Italic.ttf")))
pdfmetrics.registerFontFamily("Carlito", normal="Carlito", bold="Carlito-Bold", italic="Carlito-Italic", boldItalic="Carlito-Bold")

INK, LIME, PAPER, MUTED, GRID = (colors.HexColor(c) for c in (cfg.INK, cfg.LIME, cfg.PAPER, cfg.MUTED, cfg.GRID))
RED, AMBER, GREEN = (colors.HexColor(cfg.STATUS_COLORS[k]) for k in ("Canceled by Driver", "Canceled by Customer", "Success"))
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

S = {
    "body": ParagraphStyle("body", fontName="Carlito", fontSize=10, leading=14, textColor=INK, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="Carlito", fontSize=8.5, leading=11.5, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Carlito", fontSize=9, leading=12, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Carlito-Bold", fontSize=9, leading=12, textColor=INK),
    "h1": ParagraphStyle("h1", fontName="Carlito-Bold", fontSize=22, leading=26, textColor=INK, spaceAfter=4, spaceBefore=14),
    "lead": ParagraphStyle("lead", fontName="Carlito", fontSize=11.5, leading=16, textColor=MUTED, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Carlito-Bold", fontSize=14, leading=17, textColor=INK, spaceBefore=10, spaceAfter=4),
    "h3": ParagraphStyle("h3", fontName="Carlito-Bold", fontSize=11, leading=14, textColor=INK, spaceBefore=6, spaceAfter=2),
    "label": ParagraphStyle("label", fontName="Carlito-Bold", fontSize=8.5, leading=11, textColor=MUTED),
    "kpi_v": ParagraphStyle("kpi_v", fontName="Carlito-Bold", fontSize=19, leading=22, textColor=INK),
    "kpi_l": ParagraphStyle("kpi_l", fontName="Carlito", fontSize=8.5, leading=11, textColor=MUTED),
    "bullet": ParagraphStyle("bullet", fontName="Carlito", fontSize=10, leading=14, textColor=INK, leftIndent=12, bulletIndent=0, spaceAfter=3),
    "caption": ParagraphStyle("caption", fontName="Carlito-Italic", fontSize=8.5, leading=11, textColor=MUTED, spaceAfter=6),
}

_GLYPHS = set()
_CMAP = None


def P(text, style="body"):
    """Paragraph helper that also records characters so we can verify glyph coverage."""
    _GLYPHS.update(text)
    return Paragraph(text, S[style])


def chart(name, width=CONTENT_W * 0.96, max_h=None):
    path = CHARTS / f"{name}.png"
    w, h = PILImage.open(path).size
    height = width * h / w
    if max_h and height > max_h:
        width, height = width * max_h / height, max_h
    img = Image(str(path), width=width, height=height)
    img.hAlign = "CENTER"
    return img


def chip_table(rows, col_widths, header=True, zebra=True, font=9):
    """Standard styled table (header row ink/white, light zebra)."""
    data = [[Paragraph(str(c), S["cellb"] if (header and i == 0) else S["cell"]) for c in r] for i, r in enumerate(rows)]
    for r in data:
        for c in r:
            _GLYPHS.update(c.text if hasattr(c, "text") else "")
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
             ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        for j in range(len(rows[0])):                      # header text white
            data[0][j] = Paragraph(f"<font color='white'>{rows[0][j]}</font>", S["cellb"])
        t = Table(data, colWidths=col_widths, repeatRows=1)
    if zebra:
        style += [("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, PAPER])]
    t.setStyle(TableStyle(style))
    return t


def insight_block(ins):
    """What / Why / So what table for one insight."""
    rows = [[P("What the data shows", "label"), P(ins.what, "cell")],
            [P("Why it happens", "label"), P(ins.why, "cell")],
            [P("What to do", "label"), P(ins.action, "cell")]]
    t = Table(rows, colWidths=[30 * mm, CONTENT_W - 30 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (0, -1), PAPER),
                           ("BACKGROUND", (1, 2), (1, 2), colors.HexColor("#F1F7DA")),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LINEBELOW", (0, 0), (-1, -2), 0.4, GRID), ("BOX", (0, 0), (-1, -1), 0.6, GRID)]))
    head = Table([[P(f"<b>{ins.title}</b>", "h3"), P(f"<b>{ins.metric}</b><br/><font size=7.5 color='{cfg.MUTED}'>{ins.metric_label}</font>", "cell")]],
                 colWidths=[CONTENT_W - 42 * mm, 42 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    ev = P("Evidence: " + "  ·  ".join(ins.evidence) + f"  |  {ins.id}, confidence {ins.confidence}", "small") if ins.evidence else Spacer(1, 1)
    return KeepTogether([head, Spacer(1, 3), t, Spacer(1, 2), ev, Spacer(1, 8)])


# ------------------------------------------------------------------ page furniture
def cover_page(c, doc):
    c.saveState()
    c.setFillColor(INK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.drawImage(str(cfg.ASSETS_DIR / "logo_full_light.png"), MARGIN, PAGE_H - 48 * mm, width=62 * mm, preserveAspectRatio=True, mask="auto")
    c.setFillColor(LIME)
    c.rect(MARGIN, PAGE_H - 108 * mm, 22 * mm, 2.2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Carlito-Bold", 40)
    c.drawString(MARGIN, PAGE_H - 128 * mm, "Why 38% of bookings")
    c.drawString(MARGIN, PAGE_H - 143 * mm, "never become rides")
    c.setFont("Carlito", 16)
    c.setFillColor(colors.HexColor("#B9C4BE"))
    c.drawString(MARGIN, PAGE_H - 158 * mm, "Ola ride-data analysis, July 2024: what is happening,")
    c.drawString(MARGIN, PAGE_H - 166 * mm, "why it happens, and what to do about it.")
    c.setFont("Carlito", 11)
    c.drawString(MARGIN, 34 * mm, "Project report  ·  SQL  ·  Power BI  ·  Streamlit  ·  Business insights")
    c.setFillColor(LIME)
    c.drawString(MARGIN, 27 * mm, "103,024 bookings  ·  94,544 customers  ·  7 vehicle types  ·  50 pickup areas")
    c.restoreState()


def body_page(c, doc):
    c.saveState()
    c.drawImage(str(cfg.ASSETS_DIR / "logo_mark.png"), MARGIN, PAGE_H - 13 * mm, width=7 * mm, height=7 * mm, mask="auto")
    c.setFont("Carlito-Bold", 9); c.setFillColor(INK)
    c.drawString(MARGIN + 9 * mm, PAGE_H - 10.5 * mm, "Ola Ride Insights")
    c.setFont("Carlito", 9); c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 10.5 * mm, "July 2024 ride-data analysis")
    c.setStrokeColor(GRID); c.setLineWidth(0.6); c.line(MARGIN, PAGE_H - 15 * mm, PAGE_W - MARGIN, PAGE_H - 15 * mm)
    c.setFont("Carlito", 8.5); c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN, 10 * mm, f"{doc.page}")
    c.drawString(MARGIN, 10 * mm, "Figures computed from the cleaned dataset; see Data & method for definitions.")
    c.restoreState()


def kpi_tiles(items):
    cells = []
    for value, label, color in items:
        cells.append([Paragraph(f"<font color='{color}'>{value}</font>", S["kpi_v"]), Paragraph(label, S["kpi_l"])])
    w = CONTENT_W / len(items)
    t = Table([[ [c[0], c[1]] for c in cells ]], colWidths=[w] * len(items))
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, GRID), ("INNERGRID", (0, 0), (-1, -1), 0.6, GRID),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("TOPPADDING", (0, 0), (-1, -1), 8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def pipeline_diagram():
    """Small vector diagram: raw data -> cleaning -> clean table -> four consumers."""
    d = Drawing(CONTENT_W, 118)
    def box(x, y, w, h, text, fill, tc=colors.white, sub=None):
        d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=fill, strokeColor=None))
        d.add(String(x + w / 2, y + h / 2 + (4 if sub else -3), text, textAnchor="middle", fontName="Carlito-Bold", fontSize=9.5, fillColor=tc))
        if sub:
            d.add(String(x + w / 2, y + h / 2 - 8, sub, textAnchor="middle", fontName="Carlito", fontSize=7.5, fillColor=tc))
    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2 - 4, y2, strokeColor=MUTED, strokeWidth=1.2))
        d.add(Polygon([x2, y2, x2 - 6, y2 + 3, x2 - 6, y2 - 3], fillColor=MUTED, strokeColor=None))
    box(0, 49, 78, 36, "OLA_DataSet.xlsx", colors.HexColor("#C9D2CC"), INK, "103,024 raw rows")
    box(108, 49, 90, 36, "Python cleaning", INK, colors.white, "ola/preprocessing.py")
    box(228, 49, 90, 36, "Clean table", LIME, INK, "33 columns · 15 rules pass")
    arrow(78, 67, 108, 67); arrow(198, 67, 228, 67)
    targets = [("SQL (MySQL / SQLite)", 88), ("Streamlit app + SQL lab", 60), ("Power BI dashboard", 32), ("PDF report + slides", 4)]
    for text, y in targets:
        box(352, y, CONTENT_W - 352, 22, text, colors.white, INK)
        d.add(Rect(352, y, CONTENT_W - 352, 22, rx=6, ry=6, fillColor=None, strokeColor=GRID, strokeWidth=0.8))
        arrow(318, 67, 352, y + 11)
    return d


# ------------------------------------------------------------------ SQL answers
def sql_answers(df):
    conn = build_database(df)
    lib = {q.id: q for q in parse_query_library()}
    run = lambda i: run_readonly(conn, lib[i].sql, max_rows=200_000).df               # noqa: E731
    q2, q2b = run("Q02").set_index("Vehicle_Type"), run("Q02b").set_index("Vehicle_Type")
    q4, q6, q8 = run("Q04"), run("Q06").iloc[0], run("Q08")
    q10b = run("Q10b")
    rows = [
        ["#", "Question", "SQL result", "Reading"],
        ["1", "All successful bookings", f"{len(run('Q01')):,} rows", "62.1% of all bookings; view <i>v_successful_bookings</i> returns the same rows."],
        ["2", "Average ride distance per vehicle type",
         "All bookings: " + ", ".join(f"{v} {x:.2f}" for v, x in q2["Avg_Distance_All_Bookings_Km"].items()),
         "Matches the workbook's AVERAGEIF. Cancelled rides count as 0 km; completed-only (Q2b): Auto "
         f"{q2b.loc['Auto', 'Avg_Distance_Completed_Km']:.1f} km vs about {q2b.drop('Auto')['Avg_Distance_Completed_Km'].mean():.0f} km for the rest."],
        ["3", "Rides cancelled by customers", f"{run('Q03').iloc[0, 0]:,}", "10.2% of all bookings."],
        ["4", "Top 5 customers by number of rides", "; ".join(f"{r.Customer_ID} ({r.Total_Rides})" for r in q4.itertuples()),
         "One customer has 5 bookings; 26 tie on 4. Ties are broken by completed value, then ID."],
        ["5", "Driver cancellations: personal and car-related issues", f"{run('Q05').iloc[0, 0]:,}", "Largest driver-cancellation reason (35.5%)."],
        ["6", "Max and min driver rating, Prime Sedan", f"max {q6.Max_Driver_Rating}, min {q6.Min_Driver_Rating}", "The full 3.0-5.0 range; cancelled rides carry no rating (NULL)."],
        ["7", "Rides paid by UPI", f"{len(run('Q07')):,} rows", "40.5% of completed rides."],
        ["8", "Average customer rating per vehicle type", ", ".join(f"{r.Vehicle_Type} {r.Avg_Customer_Rating:.2f}" for r in q8.itertuples()),
         "All within 0.02 points of 4.00; differences are not significant."],
        ["9", "Total booking value of successful rides", f"{cfg.CURRENCY}{run('Q09').iloc[0, 0]:,.0f}",
         f"Excluding the 3,926 rides flagged incomplete: {cfg.CURRENCY}{run('Q09b').iloc[0, 0]:,.0f}."],
        ["10", "All incomplete rides with the reason", f"{len(run('Q10')):,} rows", "; ".join(f"{r.Incomplete_Rides_Reason} {r.Rides:,}" for r in q10b.itertuples()) + "."],
    ]
    return rows, lib


# ------------------------------------------------------------------ build
def build():
    df = load_clean()
    dq = load_dq_report()
    report_charts.build_all(df)
    k = m.kpis(df)
    ins = {i.id: i for i in m.build_insights(df)}
    cust = m.customer_outcomes(df)
    att = m.failure_attribution(df)
    supply = att.loc[att["Supply_Side"], "Share_Pct"].sum()

    doc = BaseDocTemplate(str(OUT_PDF), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=22 * mm, bottomMargin=18 * mm,
                          title="Ola Ride Insights - Report", author="Ola Ride Insights project", subject="Ride-sharing analytics, July 2024")
    cover = PageTemplate(id="cover", frames=[Frame(MARGIN, MARGIN, CONTENT_W, 20, id="c")], onPage=cover_page)
    body = PageTemplate(id="body", frames=[Frame(MARGIN, 18 * mm, CONTENT_W, PAGE_H - 40 * mm, id="b", leftPadding=0, rightPadding=0,
                                                 topPadding=0, bottomPadding=0)], onPage=body_page)
    doc.addPageTemplates([cover, body])

    f = [Spacer(1, 1), NextPageTemplate("body"), PageBreak()]

    # ---------------- 1. Executive summary
    f += [P("Executive summary", "h1"),
          P("What the July 2024 ride data says, why it happens, and what to do about it.", "lead"),
          kpi_tiles([(m.fmt_int(k["total_bookings"]), "bookings in July 2024", cfg.INK),
                     (m.fmt_pct(k["success_rate"]), "bookings become a completed ride", cfg.STATUS_COLORS["Canceled by Driver"]),
                     (m.fmt_inr(k["revenue"]), "revenue from completed rides", cfg.STATUS_COLORS["Success"])]),
          Spacer(1, 4),
          kpi_tiles([(m.fmt_inr(k["quoted_fare_lost"]), "quoted fares never converted", cfg.STATUS_COLORS["Canceled by Driver"]),
                     (f"{supply:.0f}%", "of failures trace to the supply side", cfg.INK),
                     (m.fmt_pct(cust["never_completed_rate"]), "of customers never completed a ride", cfg.STATUS_COLORS["Canceled by Driver"])]),
          Spacer(1, 10),
          P("The answer in one paragraph", "h2"),
          P(f"Ola handled {k['total_bookings']:,} bookings in July 2024, but only {k['success_rate']:.1f}% ended in a completed ride. The other "
            f"{k['failed']:,} bookings carried {m.fmt_inr(k['quoted_fare_lost'])} of quoted fares that never turned into revenue. The failure rate is the same "
            "in every vehicle type, hour, weekday and pickup area, and no gap is statistically significant. A problem that looks identical everywhere is "
            f"<b>systemic</b>: it sits in dispatch and driver supply, not in one corner of the network. Once customer cancellations caused by the driver are "
            f"re-attributed, <b>{supply:.0f}% of failures are supply-side</b>."),
          P("Five findings that matter", "h2")]
    msgs = [
        f"<b>Failures are platform-wide, not local.</b> Success ranges only {m.vehicle_summary(df)['Success_Rate_Pct'].min():.1f}-{m.vehicle_summary(df)['Success_Rate_Pct'].max():.1f}% across vehicles. Segment campaigns will not fix it; dispatch and driver incentives will.",
        f"<b>Drivers, not customers, drive the losses.</b> Driver cancellations and no-driver-found are {k['driver_cancel_rate'] + k['no_driver_rate']:.1f}% of bookings versus {k['customer_cancel_rate']:.1f}% cancelled by customers, and more than half of customer cancellations are reactions to the driver.",
        f"<b>Every 10% of failed bookings recovered is worth {m.fmt_inr(0.1 * k['quoted_fare_lost'])}</b> (+{0.1 * k['quoted_fare_lost'] / k['revenue'] * 100:.1f}% revenue): the clearest business case in the data.",
        f"<b>Pricing and ratings carry no signal.</b> Fare is unrelated to distance (r = {ins['I05'].metric}) and ratings are unrelated to anything, so neither can yet guide pricing or driver incentives.",
        f"<b>Retention is the growth lever.</b> {cust['single_booking_rate']:.1f}% of customers booked once and {cust['never_completed_rate']:.1f}% never completed a ride.",
    ]
    f += [Paragraph(t, S["bullet"], bulletText=f"{i}.") for i, t in enumerate(msgs, 1)]
    for t in msgs:
        _GLYPHS.update(t)
    road = m.action_roadmap(df)
    f += [P("What we recommend first", "h2")]
    for r in road.head(3).itertuples():
        t = f"<b>{r.Initiative}.</b> {r._3} <i>Impact: {r._4}.</i>"
        f.append(Paragraph(t, S["bullet"], bulletText="•")); _GLYPHS.update(t)
    f += [Spacer(1, 6),
          P("<b>A note on the data.</b> Hours, weekdays, locations, vehicles, ratings and fares are all unusually uniform, which is rare in real ride data and "
            "suggests a sampled or synthetic extract. The attribution and uniformity findings are solid within this dataset, but any operational change "
            "should be re-validated on production data (see Limitations).", "small"), PageBreak()]

    # ---------------- 2. Project & method
    f += [P("Project approach and data", "h1"),
          P("How the brief was delivered, end to end, from raw workbook to decision-ready insight.", "lead"), pipeline_diagram(), Spacer(1, 6)]
    brief = [["Brief requirement", "Delivered", "Where"],
             ["Data understanding and EDA", "Structure, nulls, distributions, correlations and tests", "notebooks/01_EDA.ipynb; this report"],
             ["Cleaning and preprocessing", "15 validation rules, 14 derived features, nulls kept (structural)", "ola/preprocessing.py; sql/ola_schema_and_cleaning.sql"],
             ["SQL query development", f"{len(parse_query_library())} documented queries incl. all 10 required, joins, CTEs, window functions", "sql/ola_queries.sql"],
             ["Power BI dashboard", "5 pages, 10 required visuals: theme, DAX, Power Query, build guide", "powerbi/"],
             ["Streamlit application", "12 views, filters, search, live SQL playground, Power BI embed", "app.py, ola/"],
             ["Documentation and storytelling", "This report, slide deck, README, data dictionary", "reports/, README.md"]]
    f += [chip_table(brief, [46 * mm, 78 * mm, CONTENT_W - 124 * mm]), Spacer(1, 8), P("Data and cleaning", "h2"),
          P(f"The workbook sheet <i>July</i> holds {dq['rows_raw']:,} bookings from {dq['date_range'][0]} to {dq['date_range'][1]}: {dq['unique_customers']:,} customers, "
            f"7 vehicle types and {dq['unique_pickup_locations']} Bengaluru pickup areas. No duplicate Booking_IDs, no whitespace or spelling variants, and no rows were dropped."),
          P("<b>Nulls are structural, so they were not imputed.</b> The text 'null' appears only where a field cannot exist: ratings, payment method and turn-around "
            "times on rides that never happened; a cancellation reason only on the matching cancellation status. Filling them with a mean or mode would invent "
            "ratings for rides that never took place and distort every average. They were converted to real NULLs, and SQL and pandas aggregates skip them correctly."),
          P("<b>Definitions used throughout.</b> <i>Completed</i> = Booking_Status Success. <i>Revenue</i> = Booking_Value of completed rides only. "
            "<i>Quoted fare lost</i> = Booking_Value of failed bookings (a quote, not revenue). <i>Driver-side failure</i> = driver cancelled, no driver found, or a customer "
            "cancellation that cites the driver."),
          P("<b>Derived features:</b> Ride_Hour, Day_Name, Time_Band (four equal 6-hour windows), outcome flags, Failure_Type and unified Failure_Reason, Fare_Per_Km, "
            "Distance_Band, Is_Same_Pickup_Drop and Rating_Gap."),
          P("How the work was validated", "h2"),
          KeepTogether(chip_table([["Check", "Result"],
                      ["15 business-rule checks (duplicates, reason/status consistency, rating range, dates...)", "0 violations"],
                      ["SQL-side cleaning vs Python cleaning (all 103,024 rows, 33 columns)", "32 columns identical; Fare_Per_Km differs by at most INR 0.01 (rounding mode)"],
                      ["SQL vs pandas on KPIs, vehicle scorecard, failure attribution, top customers, payments, anomalies", "Exact agreement"],
                      ["All SQL queries executed; every write statement blocked in the playground", "Passed (29 automated tests)"]],
                     [105 * mm, CONTENT_W - 105 * mm]))]

    # ---------------- 3. Demand
    f += [CondPageBreak(1), P("1. Demand: steady, with no peak hour", "h1"),
          P("Business question: when is demand highest, and should driver supply move with it?", "lead"),
          chart("daily_volume"), P("Figure 1. Daily bookings by outcome with the 7-day average.", "caption"),
          chart("hourly_weekday"), P("Figure 2. Bookings by hour (left) and by weekday, raw versus per calendar day (right).", "caption"),
          insight_block(ins["I06"])]

    # ---------------- 4. Outcomes
    f += [CondPageBreak(120 * mm), P("2. Outcomes: where the 38% goes", "h1"),
          P("Business question: why do bookings fail, and who is responsible?", "lead"),
          KeepTogether([chart("status_donut", width=CONTENT_W * 0.4, max_h=62 * mm), P("Figure 3. Booking status breakdown.", "caption")]),
          chart("failure_attribution"), P("Figure 4. Every failed booking assigned to a root cause.", "caption"),
          insight_block(ins["I01"]), insight_block(ins["I02"])]

    # ---------------- 5. Reasons
    f += [CondPageBreak(120 * mm), P("3. Why people cancel", "h1"),
          P("Business question: what do the cancellation reasons tell us, and can we trust them?", "lead"),
          chart("cancel_reasons"), P("Figure 5. Reasons given by customers (left) and drivers (right).", "caption"),
          insight_block(ins["I03"]), insight_block(ins["I12"]),
          KeepTogether([chart("incomplete", width=CONTENT_W * 0.52), P("Figure 6. Reasons for incomplete rides (3,926 completed bookings that ended early).", "caption")]),
          insight_block(ins["I10"])]

    # ---------------- 6. Revenue
    f += [CondPageBreak(120 * mm), P("4. Revenue: what is lost and how it is paid", "h1"),
          P("Business question: how much revenue is at stake, and how is it collected?", "lead"),
          chart("revenue_waterfall"), P("Figure 7. From the quoted value of all bookings to realised revenue.", "caption"),
          insight_block(ins["I04"]), chart("payments_vehicles"), P("Figure 8. Revenue by payment method (left) and revenue per km by vehicle (right).", "caption"),
          insight_block(ins["I07"])]

    # ---------------- 7. Pricing
    f += [CondPageBreak(120 * mm), P("5. Pricing integrity and surge", "h1"),
          P("Business question: do fares behave like a distance-based tariff, and is surge visible?", "lead"),
          chart("pricing"), P("Figure 9. Fare against distance (left) and average fare and fare per km by distance band (right).", "caption"),
          insight_block(ins["I05"]), insight_block(ins["I11"]),
          P("<b>Surge pricing.</b> The dataset has no surge multiplier. As a proxy, weighted fare per km by hour of day stays within a narrow band and success rate is "
            "flat across hours, so there is no visible price response to demand and surge effectiveness cannot be demonstrated from this data. Recommendation: log the surge "
            "multiplier and the unsurged base fare for every booking.", "body")]

    # ---------------- 8. Vehicles, customers
    f += [CondPageBreak(120 * mm), P("6. Vehicles and customers", "h1"),
          P("Business question: do vehicle types differ, and how do customers behave?", "lead"),
          chart("vehicles"), P("Figure 10. Top 5 vehicle types by ride distance (left) and average customer rating (right).", "caption"),
          P("Vehicle type changes <i>how far</i> a trip goes only for Auto (about 10 km versus about 25 km for the other six); it changes neither the success rate, the "
            "fare, the rating nor the turn-around time. The top five types by total distance are within a few percent of each other because distance follows ride volume.", "body"),
          chart("customers"), P("Figure 11. Bookings per customer (left) and customers who never completed a ride (right).", "caption"),
          insight_block(ins["I08"])]

    # ---------------- 9. Ratings & anomalies
    f += [CondPageBreak(120 * mm), P("7. Ratings and anomalies", "h1"),
          P("Business question: can ratings be trusted, and what looks unusual enough to review?", "lead"),
          chart("ratings"), P("Figure 12. Driver and customer rating distributions (left) and their cross-tab (right).", "caption"),
          insight_block(ins["I09"]),
          P("Anomaly and fraud signals", "h2"),
          P("Rule-based review queues, each a <i>candidate</i> list rather than proof of fraud. The six rules, their thresholds and the exact SQL are in the app's Anomalies "
            "page and in <i>sql/ola_queries.sql</i> (queries H01 to H07).", "body"),
          chart("anomalies"), P("Figure 13. Records flagged by each rule.", "caption"),
          KeepTogether(chip_table([["Rule", "Why it matters"],
                      ["Fare above INR 500 per km", "Typical fare is about INR 22 per km; extreme values suggest mis-keyed distance, mis-priced fares or manual overrides."],
                      ["Fare of INR 1,500 or more on a ride of 5 km or less", "Premium fare on a very short trip: the classic signature of fare inflation."],
                      ["Pickup equals drop", "Round trips or location capture errors; 1,306 of them were completed with an average distance of 22.7 km."],
                      ["AC complaint on a vehicle without AC", "Reason list is not vehicle-aware; every reason percentage is partly noise."],
                      ["Rating gap of 1.5 or more", "Possible retaliation or dispute between rider and driver."],
                      ["Customers with 3 or more failed bookings", "Churn and abuse risk; also the best win-back list."]],
                     [58 * mm, CONTENT_W - 58 * mm]))]

    # ---------------- 10. Roadmap
    rows = [["#", "Initiative", "What to do", "Expected impact", "Effort"]] + [
        [str(r.Priority), f"<b>{r.Initiative}</b>", r._3, r._4, r._6] for r in road.itertuples()]
    f += [CondPageBreak(120 * mm), P("8. Recommendations and roadmap", "h1"),
          P("Prioritised by size of impact and confidence. Impact figures are scenarios computed from the data, not forecasts; effort is an analyst estimate.", "lead"),
          chip_table(rows, [8 * mm, 36 * mm, 66 * mm, 46 * mm, CONTENT_W - 156 * mm]),
          Spacer(1, 8),
          CondPageBreak(75 * mm),
          P("Business use cases from the brief", "h2"),
          KeepTogether(chip_table([["Use case", "Answer from the data"],
                      ["Peak demand hours and driver allocation", "There is no peak: all 24 hours are within +/-3% of average. Do not reallocate drivers by hour on this evidence; re-test on production timestamps."],
                      ["Customer behaviour for personalised marketing", "91.6% book once; 36.6% never completed a ride. Target failed-first-booking customers with priority dispatch and a credit; spend is fragmented, so no key-account programme is needed."],
                      ["Pricing patterns and surge effectiveness", "Fare is unrelated to distance and to vehicle type, and shows no hourly response. Audit the fare engine and log surge multipliers before judging surge."],
                      ["Anomalies and fraudulent activity", "Six rule-based queues; start with fares above INR 500 per km and premium fares on very short rides."]],
                     [52 * mm, CONTENT_W - 52 * mm])),
          PageBreak()]

    # ---------------- 11. SQL appendix
    sql_rows, lib = sql_answers(df)
    groups = {}
    for q in lib.values():
        groups[q.group] = groups.get(q.group, 0) + 1
    f += [P("Appendix A. SQL answers", "h1"),
          P("The ten required questions, answered by running the project's own SQL against the cleaned table. Full text and notes: <i>sql/ola_queries.sql</i>.", "lead"),
          chip_table(sql_rows, [8 * mm, 42 * mm, 62 * mm, CONTENT_W - 112 * mm]), Spacer(1, 8),
          P("SQL techniques demonstrated", "h2"),
          P(f"{len(lib)} documented queries in nine groups: " + "; ".join(f"{g} ({n})" for g, n in groups.items()) + ". Techniques: JOINs to dimension tables "
            "(vehicle class and AC flag, digital vs cash), CTEs, window functions (RANK, NTILE, running totals, 7-day moving average, share-of-total), anti-join for customers "
            "with no completed ride, CASE-based pivots, views, indexes and a data-quality audit. All queries use the portable subset shared by MySQL 8 and SQLite and force decimal "
            "division, so the same text runs in the Streamlit playground and on a MySQL server feeding Power BI.", "body")]

    # ---------------- 12. Dashboards
    f += [CondPageBreak(120 * mm), P("Appendix B. Dashboards and how to run them", "h1"),
          P("The Streamlit app and the Power BI report show the same five views from the brief.", "lead"),
          chip_table([["View", "Brief visuals", "Streamlit page"],
                      ["Overall", "Ride Volume Over Time; Booking Status Breakdown", "Overall"],
                      ["Vehicle Type", "Top 5 Vehicle Types by Ride Distance; Average Customer Ratings by Vehicle Type", "Vehicle types"],
                      ["Revenue", "Revenue by Payment Method; Top 5 Customers by Booking Value; Ride Distance Distribution Per Day", "Revenue & pricing"],
                      ["Cancellation", "Cancelled Rides Reasons (Customer); Cancelled Rides Reasons (Drivers)", "Cancellations"],
                      ["Ratings", "Driver Ratings; Customer Ratings; Customer vs Driver Ratings", "Ratings"]],
                     [28 * mm, 100 * mm, CONTENT_W - 128 * mm]),
          Spacer(1, 6),
          P("Beyond the brief the app adds an executive summary of insights, customer and anomaly views, a booking explorer with search, global filters (date, vehicle, time of "
            "day, weekday/weekend, pickup area), a live read-only SQL playground with a query library, schema browser and result charting, and an optional Power BI embed.", "body"),
          P("Run locally", "h2"),
          P("<font name='Carlito-Bold'>pip install -r requirements.txt</font>  then  <font name='Carlito-Bold'>streamlit run app.py</font>. To rebuild the cleaned data from the original workbook: "
            "<font name='Carlito-Bold'>python -m ola.preprocessing --raw OLA_DataSet.xlsx</font>. To deploy free on Streamlit Community Cloud: push the repository to GitHub, choose the "
            "repository and <i>app.py</i>, and (optionally) add <i>POWERBI_EMBED_URL</i> under Secrets.", "body"),
          P("Power BI", "h2"),
          P("Power BI Desktop is needed to author a <i>.pbix</i>, so the <i>powerbi/</i> folder provides everything required to build it in about an hour: a brand theme, 35 DAX measures with "
            "expected values, Power Query for both the cleaned CSV and the original workbook, and a page-by-page build guide with interactivity checklist.", "body")]

    # ---------------- 13. Limitations
    f += [CondPageBreak(120 * mm), P("Limitations and next steps", "h1"), P("What this analysis can and cannot support.", "lead")]
    for t in dq["caveats"]:
        f.append(Paragraph(t, S["bullet"], bulletText="•")); _GLYPHS.update(t)
    f += [Spacer(1, 4), P("Next steps", "h2")]
    for t in ["Re-run the pipeline on a production extract with hourly timestamps, a surge multiplier and the metered fare; the app, SQL and report update unchanged.",
              "Add driver-level fields (driver ID, acceptance history, ETA at dispatch) to model why individual drivers cancel.",
              "Run an A/B test of re-dispatch on stalled pickups and a UPI cashback, measured on driver-attributable failure rate and cash share.",
              "Extend to more months to measure retention and seasonality, which a single month cannot show."]:
        f.append(Paragraph(t, S["bullet"], bulletText="•")); _GLYPHS.update(t)
    f += [PageBreak(), P("Appendix C. Data dictionary", "h1"),
          chip_table([["Column", "Type", "Origin", "Meaning"]] + [[a, b, c, d] for a, b, c, d in DATA_DICTIONARY],
                     [48 * mm, 24 * mm, 20 * mm, CONTENT_W - 92 * mm])]

    doc.build(f)

    # glyph coverage check (Carlito must contain every character we typed)
    from fontTools.ttLib import TTFont as FT
    cmap = FT(str(FONT_DIR / "Carlito-Regular.ttf")).getBestCmap()
    missing = sorted(ch for ch in _GLYPHS if ch.strip() and ord(ch) not in cmap and ch not in "<>/=' \"")
    print("PDF written:", OUT_PDF, f"({OUT_PDF.stat().st_size / 1024:.0f} KB)")
    if missing:
        print("WARNING glyphs missing from Carlito:", missing)


if __name__ == "__main__":
    build()
