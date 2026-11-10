/**
 * scripts/build_pptx.js
 * =====================
 * Builds reports/OLA_Ride_Insights_Presentation.pptx (15 slides, 16:9).
 *
 * Structure: theme -> layouts (title / content / dark) with a named title placeholder -> sections.
 * Charts are native PowerPoint charts (editable); the revenue waterfall is drawn with shapes
 * because PowerPoint has no waterfall chart type in pptxgenjs.
 * Every number comes from reports/deck_data.json (python scripts/export_deck_data.py).
 *
 * Run:  python scripts/export_deck_data.py && node scripts/build_pptx.js
 */
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/mnt/skills/public/pptx/scripts/apply_theme.js");

const ROOT = path.resolve(__dirname, "..");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "reports", "deck_data.json"), "utf8"));
const OUT = path.join(ROOT, "reports", "OLA_Ride_Insights_Presentation.pptx");
const LOGO_FULL_LIGHT = path.join(ROOT, "assets", "logo_full_light.png");
const LOGO_MARK = path.join(ROOT, "assets", "logo_mark.png");

// ---------------------------------------------------------------- palette & type
const INK = "0F1A17", LIME = "C6E22A", PAPER = "F4F6F1", MUTED = "5E6B66", GRID = "E3E8DF", WHITE = "FFFFFF";
const GREEN = "1F9D6B", RED = "E4572E", AMBER = "F2A93B", SLATE = "6B7A99", BLUE = "3D5A80", PURPLE = "8E7DBE";
const HEAD = "Cambria", BODY = "Calibri";
const THEME = {
  name: "Ola Ride Insights", headFontFace: HEAD, bodyFontFace: BODY,
  colors: { dk1: INK, lt1: WHITE, dk2: "1B2A26", lt2: PAPER, accent1: GREEN, accent2: RED, accent3: AMBER,
            accent4: SLATE, accent5: LIME, accent6: BLUE, hlink: BLUE, folHlink: PURPLE },
};

const fmtM = (v, d = 2) => `₹${(v / 1e6).toFixed(d)}M`;
const fmtInt = (v) => Math.round(v).toLocaleString("en-US");

// ---------------------------------------------------------------- deck + layouts
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";                          // 10in x 5.625in
pres.title = "Ola Ride Insights";
pres.author = "Ola Ride Insights project";
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };

const footer = (color) => ({ text: { text: "Ola Ride Insights  ·  July 2024", options: { x: 0.5, y: 5.2, w: 4, h: 0.25, fontFace: BODY, fontSize: 9, color } } });
pres.defineSlideMaster({
  title: "CONTENT", background: { color: WHITE },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.32, w: 9, h: 0.95, fontFace: HEAD, fontSize: 25, bold: true, color: INK, align: "left", valign: "top", margin: 0 }, text: "" } },
    footer(MUTED),
  ],
  slideNumber: { x: 9.1, y: 5.2, fontFace: BODY, fontSize: 9, color: MUTED },
});
pres.defineSlideMaster({
  title: "DARK", background: { color: INK },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.5, w: 8.8, h: 1.5, fontFace: HEAD, fontSize: 30, bold: true, color: WHITE, align: "left", valign: "top", margin: 0 }, text: "" } },
    footer("9FB0A8"),
  ],
  slideNumber: { x: 9.1, y: 5.2, fontFace: BODY, fontSize: 9, color: "9FB0A8" },
});

pres.defineSlideMaster({
  title: "TITLE", background: { color: INK },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.75, w: 8.8, h: 1.7, fontFace: HEAD, fontSize: 42, bold: true, color: WHITE, align: "left", valign: "top", margin: 0 }, text: "" } }],
});

// ---------------------------------------------------------------- helpers
const T = (slide, text, o) => slide.addText(text, Object.assign({ isTextBox: true, fontFace: BODY, color: INK, margin: 0 }, o));

/** Rounded stat card: big number, small label. */
function statCard(slide, x, y, w, h, value, label, valueColor = INK, name = "stat") {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: PAPER }, line: { color: PAPER }, rectRadius: 0.12, objectName: `${name} card` });
  T(slide, value, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: h * 0.5, fontFace: HEAD, fontSize: 30, bold: true, color: valueColor, valign: "middle", objectName: `${name} value` });
  T(slide, label, { x: x + 0.2, y: y + h * 0.58, w: w - 0.4, h: h * 0.36, fontSize: 12, color: MUTED, valign: "top", objectName: `${name} label` });
}

/** Shared native-chart styling so every chart looks the same. */
const chartBase = (extra = {}) => Object.assign({
  showTitle: false, showLegend: false,
  catAxisLabelFontFace: BODY, catAxisLabelFontSize: 10, catAxisLabelColor: MUTED,
  valAxisLabelFontFace: BODY, valAxisLabelFontSize: 10, valAxisLabelColor: MUTED,
  valGridLine: { color: GRID, size: 0.75 }, catGridLine: { style: "none" },
  dataLabelFontFace: BODY, dataLabelFontSize: 10, dataLabelColor: INK,
  legendFontFace: BODY, legendFontSize: 10, legendColor: MUTED,
}, extra);

const heading = (slide, text, x, y, w) => T(slide, text, { x, y, w, h: 0.3, fontFace: HEAD, fontSize: 13, bold: true, color: INK });
const caption = (slide, text, x, y, w, h = 0.5) => T(slide, text, { x, y, w, h, fontSize: 11, color: MUTED, valign: "top" });
const bullets = (slide, items, x, y, w, h, size = 14) => slide.addText(
  items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 8 } })),
  { isTextBox: true, x, y, w, h, fontFace: BODY, fontSize: size, color: INK, valign: "top", margin: 0 });

// ================================================================ 1. Title
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Introduction" });
s.addImage({ path: LOGO_FULL_LIGHT, x: 0.6, y: 0.45, w: 2.3, h: 0.905, altText: "Ola Ride Insights logo" });
s.addText("Why 38% of bookings never become rides", { placeholder: "title" });
T(s, "Ola ride-data analysis, July 2024: what is happening, why it happens, and what to do about it", { x: 0.6, y: 3.55, w: 7.4, h: 0.8, fontSize: 18, color: "B9C4BE" });
T(s, `${fmtInt(D.kpi.total_bookings)} bookings  ·  ${fmtInt(D.kpi.unique_customers)} customers  ·  7 vehicle types  ·  50 pickup areas`, { x: 0.6, y: 4.55, w: 8.8, h: 0.3, fontSize: 13, color: LIME });
s.addNotes("Open with the question: if demand is steady and healthy, why does 38% of it never turn into a ride? The rest of the deck answers that in four steps: where it fails, who is responsible, what it costs, and what to change first.");

// ================================================================ 2. Executive summary
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Only 62% of bookings complete, and most of the loss is a driver-supply problem", { placeholder: "title" });
const cw = 2.1, cg = 0.2;
statCard(s, 0.5, 1.5, cw, 1.45, `${D.kpi.success_rate.toFixed(1)}%`, "of bookings become a completed ride", RED, "success");
statCard(s, 0.5 + (cw + cg), 1.5, cw, 1.45, fmtM(D.kpi.quoted_fare_lost), "of quoted fares never converted", RED, "lost");
statCard(s, 0.5 + 2 * (cw + cg), 1.5, cw, 1.45, `${D.kpi.supply_share.toFixed(0)}%`, "of failures trace back to the supply side", INK, "supply");
statCard(s, 0.5 + 3 * (cw + cg), 1.5, cw, 1.45, `${D.cust.never_completed_rate.toFixed(1)}%`, "of customers never completed a ride", RED, "never");
bullets(s, [
  `Failure is uniform across vehicles (${D.tests.succ_min.toFixed(1)}-${D.tests.succ_max.toFixed(1)}% success), hours, weekdays and areas, so the cause is systemic: dispatch and driver supply.`,
  `Every 10% of failed bookings recovered is worth ${fmtM(D.kpi.recover10)} (+${D.kpi.recover10_pct.toFixed(1)}% revenue).`,
  "Fares ignore distance and ratings relate to nothing, so neither can guide decisions yet.",
], 0.5, 3.3, 9, 1.7, 15);
s.addNotes("Four numbers carry the story. The failure rate looks the same in every segment, which is the key clue: it is a platform-wide problem, not a local one. The 88% figure re-attributes customer cancellations that were caused by the driver.");

// ================================================================ 3. Approach
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("One clean dataset feeds SQL, Power BI, a Streamlit app and this report", { placeholder: "title" });
const cards = [
  ["SQL", ["58 documented queries incl. all 10 required", "Joins, CTEs, window functions, anti-join", "Validated against pandas, runs on MySQL 8 and SQLite"]],
  ["Power BI", ["5 pages, 10 required visuals", "Theme, 35 DAX measures, Power Query", "Step-by-step build guide"]],
  ["Streamlit", ["12 interactive views with filters and search", "Live read-only SQL playground", "Insight cards: what, why, so what"]],
];
cards.forEach(([h, items], i) => {
  const x = 0.5 + i * 3.05;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.45, w: 2.85, h: 2.2, fill: { color: PAPER }, line: { color: PAPER }, rectRadius: 0.12, objectName: `${h} card` });
  T(s, h, { x: x + 0.2, y: 1.58, w: 2.45, h: 0.35, fontFace: HEAD, fontSize: 17, bold: true });
  bullets(s, items, x + 0.2, 2.05, 2.5, 1.5, 12);
});
// pipeline strip
const steps = [["Raw workbook", "103,024 rows"], ["Python cleaning", "15 rules pass"], ["Clean table", "33 columns"], ["Insights", "SQL · BI · app · report"]];
steps.forEach(([a, b], i) => {
  const x = 0.5 + i * 2.3;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 4.0, w: 1.9, h: 0.85, fill: { color: i === 2 ? LIME : INK }, line: { color: i === 2 ? LIME : INK }, rectRadius: 0.1, objectName: `pipeline ${a}` });
  T(s, a, { x: x + 0.1, y: 4.08, w: 1.7, h: 0.4, fontSize: 13, bold: true, color: i === 2 ? INK : WHITE, align: "center", valign: "middle" });
  T(s, b, { x: x + 0.1, y: 4.45, w: 1.7, h: 0.3, fontSize: 10, color: i === 2 ? INK : "B9C4BE", align: "center", valign: "middle" });
  if (i < steps.length - 1) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 1.93, y: 4.28, w: 0.33, h: 0.28, fill: { color: MUTED }, line: { color: MUTED }, objectName: "pipeline arrow" });
});
s.addNotes("Everything is built from one cleaned table so the SQL, the dashboards and the report always agree. Nulls were kept, not imputed, because they are structural: a cancelled ride has no rating.");

// ================================================================ 4. Demand
pres.addSection({ title: "Findings" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Demand is steady at about 3,300 bookings every day", { placeholder: "title" });
s.addChart(pres.charts.LINE, [
  { name: "Bookings", labels: D.daily.labels.map((l) => String(parseInt(l, 10))), values: D.daily.bookings },
  { name: "7-day average", labels: D.daily.labels.map((l) => String(parseInt(l, 10))), values: D.daily.avg7 },
], chartBase({ x: 0.4, y: 1.4, w: 6.1, h: 3.6, chartColors: [AMBER, INK], lineSize: 2, lineDataSymbol: "none", showLegend: true, legendPos: "b",
  valAxisMinVal: 0, valAxisMaxVal: 4000, catAxisLabelFontSize: 9, showCatAxisTitle: true, catAxisTitle: "Day of July 2024", catAxisTitleFontSize: 10, catAxisTitleColor: MUTED, showValAxisTitle: true, valAxisTitle: "Bookings per day", valAxisTitleFontSize: 10, valAxisTitleColor: MUTED }));
statCard(s, 6.8, 1.5, 2.7, 1.1, fmtInt(D.daily.mean), "bookings per day on average", INK, "avg");
statCard(s, 6.8, 2.75, 2.7, 1.1, `${D.daily.cv.toFixed(1)}%`, "day-to-day variation", INK, "cv");
caption(s, "No growth or decay inside the month: the lever is conversion, not demand.", 6.8, 4.0, 2.7, 0.8);
s.addNotes("Demand is remarkably stable, with variation of only about two percent day to day. That means conversion, not demand generation, is the lever.");

// ================================================================ 5. Peak hours
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("No rush hour, and the Monday-Wednesday 'peak' is a calendar artefact", { placeholder: "title" });
heading(s, "Bookings by hour of day", 0.5, 1.4, 4.4);
s.addChart(pres.charts.BAR, [{ name: "Bookings", labels: D.hourly.labels, values: D.hourly.values }],
  chartBase({ x: 0.4, y: 1.7, w: 4.5, h: 2.5, barDir: "col", chartColors: [INK], barGapWidthPct: 25, valAxisMinVal: 0, valAxisMaxVal: 6000, catAxisLabelFontSize: 8 }));
caption(s, `Every hour is within ±${D.hourly.spread.toFixed(1)}% of the ${fmtInt(D.hourly.mean)} average.`, 0.5, 4.3, 4.4, 0.6);
heading(s, "Average bookings per calendar day", 5.2, 1.4, 4.4);
s.addChart(pres.charts.BAR, [{ name: "Per day", labels: D.weekday.labels, values: D.weekday.perday }],
  chartBase({ x: 5.1, y: 1.7, w: 4.5, h: 2.5, barDir: "col", chartColors: [GREEN], barGapWidthPct: 40, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", valAxisMinVal: 0, valAxisMaxVal: 4500 }));
caption(s, "Raw totals look ~25% higher Mon-Wed only because July 2024 had five of each. Per day, every weekday is equal.", 5.2, 4.3, 4.4, 0.7);
s.addNotes("Two traps avoided. First, no hourly peak: a uniformity test cannot reject flat demand. Second, the weekday pattern in raw totals is just the calendar: 31 days is four weeks plus three extra days, Monday to Wednesday. This also means hour-based driver reallocation is not supported by this data.");

// ================================================================ 6. Outcomes
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Only 62% of bookings end in a ride, and drivers account for most of the rest", { placeholder: "title" });
s.addChart(pres.charts.DOUGHNUT, [{ name: "Status", labels: D.status.labels, values: D.status.values }],
  chartBase({ x: 0.4, y: 1.4, w: 5.0, h: 3.6, holeSize: 58, chartColors: [GREEN, AMBER, RED, SLATE], showPercent: true, showValue: false, showLegend: true, legendPos: "r",
    dataLabelColor: WHITE, dataLabelFontSize: 11, dataBorder: { pt: 2, color: WHITE } }));
statCard(s, 5.8, 1.5, 3.7, 1.0, `${(D.kpi.driver_cancel_rate + D.kpi.no_driver_rate).toFixed(1)}%`, "driver cancelled or no driver found", RED, "driver");
statCard(s, 5.8, 2.65, 3.7, 1.0, `${D.kpi.customer_cancel_rate.toFixed(1)}%`, "cancelled by customers", AMBER, "customer");
caption(s, "Driver-side failures are nearly three times customer cancellations.", 5.8, 3.85, 3.7, 0.8);
s.addNotes("Driver cancellations plus no-driver-found are 27.7 percent of all bookings, against 10.2 percent for customers. But that understates the supply problem, as the next slide shows.");

// ================================================================ 7. Attribution
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("About 88% of failures trace back to the supply side", { placeholder: "title" });
const attLabels = ["Driver cancelled", "No driver found", "Customer cancelled: driver-triggered", "Customer cancelled: own reason"];
s.addChart(pres.charts.BAR, [{ name: "Failed bookings", labels: attLabels, values: D.attribution.values }],
  chartBase({ x: 0.4, y: 1.4, w: 5.9, h: 3.5, barDir: "bar", valGridLine: { style: "none" }, chartColors: [RED, RED, RED, AMBER], barGapWidthPct: 35, catAxisOrientation: "maxMin", valAxisHidden: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", valAxisMaxVal: 24000, catAxisLabelFontSize: 11 }));
T(s, `${D.kpi.supply_share.toFixed(0)}%`, { x: 6.7, y: 1.5, w: 2.8, h: 0.9, fontFace: HEAD, fontSize: 54, bold: true, color: RED });
T(s, "of failed bookings are driver-side (red bars)", { x: 6.7, y: 2.4, w: 2.8, h: 0.5, fontSize: 13, color: MUTED });
bullets(s, ["A customer who cancels because the driver is stalled or asks them to cancel is reacting to a supply failure.", `Success is ${D.tests.succ_min.toFixed(1)}-${D.tests.succ_max.toFixed(1)}% for every vehicle type: the problem is platform-wide.`], 6.7, 3.0, 2.8, 2.0, 12);
s.addNotes("The platform records 'driver is not moving towards pickup' and 'driver asked to cancel' as customer cancellations. Re-attributing them moves the supply-side share from 28 to 88 percent. Recommend tracking a driver-attributable failure rate.");

// ================================================================ 8. Reasons
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Customers cancel because of drivers, and drivers cancel citing riders", { placeholder: "title" });
heading(s, "Why customers cancel (% of cancellations)", 0.5, 1.4, 4.4);
s.addChart(pres.charts.BAR, [{ name: "Share", labels: D.cust_reasons.labels, values: D.cust_reasons.share }],
  chartBase({ x: 0.3, y: 1.7, w: 4.6, h: 2.7, barDir: "bar", valGridLine: { style: "none" }, chartColors: [RED, RED, AMBER, AMBER, AMBER], barGapWidthPct: 35, catAxisOrientation: "maxMin", valAxisHidden: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMaxVal: 40, catAxisLabelFontSize: 9 }));
caption(s, `${D.cust_reasons.driver_triggered.toFixed(1)}% are triggered by the driver (red).`, 0.5, 4.45, 4.4, 0.5);
heading(s, "Why drivers cancel (% of cancellations)", 5.2, 1.4, 4.4);
s.addChart(pres.charts.BAR, [{ name: "Share", labels: D.drv_reasons.labels, values: D.drv_reasons.share }],
  chartBase({ x: 5.0, y: 1.7, w: 4.6, h: 2.7, barDir: "bar", valGridLine: { style: "none" }, chartColors: [RED, PURPLE, PURPLE, PURPLE], barGapWidthPct: 35, catAxisOrientation: "maxMin", valAxisHidden: true,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMaxVal: 48, catAxisLabelFontSize: 9 }));
caption(s, `${D.drv_reasons.rider_side.toFixed(1)}% cite the rider (purple), but 'customer related issue' is too vague to act on.`, 5.2, 4.45, 4.4, 0.6);
s.addNotes("Two data-quality points sit behind these charts. 'Customer related issue' is a catch-all. And 43.8 percent of 'AC is not working' cancellations came from bikes, eBikes and autos, which have no AC, so the reason list is not vehicle-aware.");

// ================================================================ 9. Revenue leakage (shapes waterfall)
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText(`Failed bookings leave ${fmtM(D.kpi.quoted_fare_lost, 1)} of quoted fares unrealised`, { placeholder: "title" });
{
  const base = 4.55, maxH = 2.7, scale = maxH / D.kpi.potential_value, bw = 0.85, x0 = 0.7, step = 1.15;
  const bars = [["Quoted value\nof all bookings", D.kpi.potential_value, 0, INK, fmtM(D.kpi.potential_value)]];
  let run = D.kpi.potential_value;
  [["Driver\ncancellations", D.leak.driver], ["Customer\ncancellations", D.leak.customer], ["No driver\nfound", D.leak.nodriver]].forEach(([l, v]) => {
    run -= v; bars.push([l, v, run, RED, `-${fmtM(v)}`]);
  });
  bars.push(["Realised\nrevenue", D.kpi.revenue, 0, GREEN, fmtM(D.kpi.revenue)]);
  bars.forEach(([label, val, bottom, color, text], i) => {
    const h = val * scale, x = x0 + i * step, y = base - bottom * scale - h;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: bw, h, fill: { color }, line: { color }, objectName: `waterfall bar ${i + 1}` });
    T(s, text, { x: x - 0.15, y: y - 0.3, w: bw + 0.3, h: 0.26, fontSize: 11, bold: true, align: "center", valign: "bottom" });
    T(s, label, { x: x - 0.15, y: base + 0.08, w: bw + 0.3, h: 0.45, fontSize: 10, color: MUTED, align: "center", valign: "top" });
  });
  s.addShape(pres.shapes.LINE, { x: 0.55, y: base, w: 5.9, h: 0, line: { color: GRID, width: 1 }, objectName: "waterfall baseline" });
}
statCard(s, 6.9, 1.5, 2.6, 1.15, `${(D.kpi.quoted_fare_lost / D.kpi.potential_value * 100).toFixed(1)}%`, "of quoted value never converts", RED, "leak");
statCard(s, 6.9, 2.8, 2.6, 1.15, fmtM(D.kpi.recover10), `recovering just 10% adds +${D.kpi.recover10_pct.toFixed(1)}% revenue`, GREEN, "recover");
caption(s, "Failed and completed bookings have the same average fare, so the loss is spread evenly, not concentrated in cheap rides.", 6.9, 4.1, 2.6, 1.0);
s.addNotes("Quoted fare on a failed booking is a quote, not revenue. Even a modest recovery rate is a large number, which makes driver-cancellation recovery the first business case.");

// ================================================================ 10. Pricing
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Fares ignore distance, so price per km collapses on long rides", { placeholder: "title" });
s.addChart(pres.charts.SCATTER, [{ name: "Distance (km)", values: D.pricing.x }, { name: "Fare (₹)", values: D.pricing.y }],
  chartBase({ x: 0.4, y: 1.4, w: 5.6, h: 3.6, chartColors: [INK], lineSize: 0, lineDataSymbolSize: 4, showCatAxisTitle: true, catAxisTitle: "Ride distance (km)",
    showValAxisTitle: true, valAxisTitle: "Fare (₹)", catAxisTitleFontSize: 10, valAxisTitleFontSize: 10, catAxisTitleColor: MUTED, valAxisTitleColor: MUTED,
    valAxisMinVal: 0, catAxisMinVal: 0, catAxisMaxVal: 50, valGridLine: { color: GRID, size: 0.75 }, catGridLine: { color: GRID, size: 0.75 } }));
statCard(s, 6.3, 1.5, 3.2, 1.0, D.pricing.corr.toFixed(3), "correlation between fare and distance", RED, "corr");
statCard(s, 6.3, 2.65, 3.2, 1.0, `₹${Math.min(...D.pricing.band_avg_fare)}-${Math.max(...D.pricing.band_avg_fare)}`, "average fare in every distance band", INK, "bandfare");
statCard(s, 6.3, 3.8, 3.2, 1.0, `${(D.pricing.auto_fpk / D.pricing.others_fpk).toFixed(1)}x`, `Auto earns more per km (${D.pricing.auto_km.toFixed(0)} km trips vs ${D.pricing.others_km.toFixed(0)} km)`, INK, "auto");
s.addNotes("In a distance-based tariff this scatter would slope upward. It is a flat cloud, and the median fare is the same for a bike, an auto and an SUV. Either Booking_Value is not the metered fare, or the fare engine is not using distance: audit it before any surge or tariff decision. The data also has no surge multiplier, so surge effectiveness cannot be measured.");

// ================================================================ 11. Payments & customers
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Cash still carries over half of revenue, and most customers book only once", { placeholder: "title" });
heading(s, "Revenue by payment method (₹ million)", 0.5, 1.4, 4.4);
s.addChart(pres.charts.BAR, [{ name: "Revenue", labels: D.payments.labels, values: D.payments.values }],
  chartBase({ x: 0.4, y: 1.7, w: 4.5, h: 2.6, barDir: "col", chartColors: [AMBER, GREEN, BLUE, PURPLE], barGapWidthPct: 40, showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 24, valAxisHidden: true }));
caption(s, `Cash ${D.payments.share[0].toFixed(1)}%, UPI ${D.payments.share[1].toFixed(1)}%. Average fare is the same for every method, so one flat digital incentive fits all riders.`, 0.5, 4.35, 4.4, 0.8);
heading(s, "Customers by number of bookings in July", 5.2, 1.4, 4.4);
s.addChart(pres.charts.BAR, [{ name: "Customers", labels: D.freq.labels, values: D.freq.values }],
  chartBase({ x: 5.1, y: 1.7, w: 4.5, h: 2.6, barDir: "col", chartColors: [INK], barGapWidthPct: 40, showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "#,##0", valAxisMinVal: 0, valAxisMaxVal: 110000, valAxisHidden: true }));
caption(s, `${D.cust.single_booking_rate.toFixed(1)}% booked once, and ${D.cust.never_completed_rate.toFixed(1)}% never completed a ride: retention is the growth lever.`, 5.2, 4.35, 4.4, 0.8);
s.addNotes("Cash is a collection and reconciliation risk. For customers, a failed first booking has no second chance in the data, so a priority-dispatch and credit win-back flow is the cheapest growth lever. The five largest customers are 0.09 percent of revenue, so there are no key accounts to protect.");

// ================================================================ 12. Ratings
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Ratings are evenly spread and relate to nothing, so they cannot guide incentives", { placeholder: "title" });
s.addChart(pres.charts.BAR, [{ name: "Driver", labels: D.ratings.labels, values: D.ratings.driver }, { name: "Customer", labels: D.ratings.labels, values: D.ratings.customer }],
  chartBase({ x: 0.4, y: 1.4, w: 6.0, h: 3.6, barDir: "col", chartColors: [INK, LIME], barGapWidthPct: 30, showLegend: true, legendPos: "t", valAxisMinVal: 0,
    catAxisLabelFontSize: 8, showValAxisTitle: true, valAxisTitle: "Completed rides", valAxisTitleFontSize: 10, valAxisTitleColor: MUTED, showCatAxisTitle: true, catAxisTitle: "Rating", catAxisTitleFontSize: 10, catAxisTitleColor: MUTED }));
statCard(s, 6.7, 1.5, 2.8, 1.0, D.ratings.corr.toFixed(3), "driver vs customer rating correlation", INK, "rcorr");
statCard(s, 6.7, 2.65, 2.8, 1.0, "3.0", "lowest rating ever given: a floor", INK, "floor");
statCard(s, 6.7, 3.8, 2.8, 1.0, `${D.ratings.low_pct.toFixed(1)}%`, "of rides rated 3.5 or lower", INK, "low");
s.addNotes("Ratings are flat from 3.0 to 5.0, show no relationship with distance, fare, wait time or vehicle, and the two sides' scores are independent. A score that does not react to service quality is not safe to use for driver incentives.");

// ================================================================ 13. Anomalies
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Findings" });
s.addText("Six rule-based queues show where to look for fare inflation and bad data", { placeholder: "title" });
const aLabels = D.anomalies.labels.map((l, i) => `${l}`);
s.addChart(pres.charts.BAR, [{ name: "Flagged", labels: aLabels, values: D.anomalies.values }],
  chartBase({ x: 0.4, y: 1.4, w: 6.2, h: 3.6, barDir: "bar", valGridLine: { style: "none" }, chartColors: [AMBER], barGapWidthPct: 35, catAxisOrientation: "maxMin", valAxisHidden: true, showValue: true,
    dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", valAxisMaxVal: 6000, catAxisLabelFontSize: 10 }));
bullets(s, ["Fares above ₹500/km and premium fares on rides under 5 km are the strongest fare-inflation signatures.",
            "AC complaints on bikes, eBikes and autos show the reason list is not vehicle-aware.",
            "A flag is a reason to look, not proof of fraud."], 6.9, 1.6, 2.6, 3.2, 12);
s.addNotes("Each rule is a candidate list for review, with the exact SQL in the query file and an exportable queue in the app. Start with the fare-based rules.");

// ================================================================ 14. Roadmap
pres.addSection({ title: "Actions" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Actions" });
s.addText("Eight initiatives, starting with driver-side failures", { placeholder: "title" });
const hdr = (t) => ({ text: t, options: { bold: true, color: WHITE, fill: { color: INK }, fontFace: BODY, fontSize: 11 } });
const rows = [[hdr("#"), hdr("Initiative"), hdr("Expected impact"), hdr("Effort")]];
D.roadmap.forEach((r, i) => rows.push([
  { text: String(r.p), options: { fontFace: BODY, fontSize: 11, fill: { color: i % 2 ? PAPER : WHITE } } },
  { text: r.initiative, options: { bold: true, fontFace: BODY, fontSize: 11, fill: { color: i % 2 ? PAPER : WHITE } } },
  { text: r.impact.replace("₹", "₹"), options: { fontFace: BODY, fontSize: 11, fill: { color: i % 2 ? PAPER : WHITE } } },
  { text: r.effort, options: { fontFace: BODY, fontSize: 11, fill: { color: i % 2 ? PAPER : WHITE } } },
]));
s.addTable(rows, { x: 0.5, y: 1.3, w: 9, colW: [0.45, 2.6, 5.2, 0.75], rowH: 0.4, border: { type: "solid", color: GRID, pt: 0.75 }, valign: "middle", margin: [0.03, 0.08, 0.03, 0.08], color: INK });
s.addNotes("Impact figures are scenarios computed from the data, not forecasts. Effort is an analyst estimate. The first three initiatives address about nine tenths of the failure problem.");

// ================================================================ 15. Conclusion
s = pres.addSlide({ masterName: "DARK", sectionTitle: "Actions" });
s.addText("Fix dispatch first: every 10% of failed bookings recovered is worth " + fmtM(D.kpi.recover10), { placeholder: "title", fontSize: 30 });
const nexts = [["1", "Cut driver-side failures", "Re-dispatch stalled pickups, acceptance incentives, cancellation penalties."],
               ["2", "Win back failed first bookings", `${fmtInt(D.cust.never_completed)} customers never got a ride.`],
               ["3", "Audit pricing and fix the data", "Fare engine, vehicle-aware reasons, rating redesign."]];
nexts.forEach(([n, h, t], i) => {
  const x = 0.6 + i * 3.0;
  s.addShape(pres.shapes.OVAL, { x, y: 2.35, w: 0.5, h: 0.5, fill: { color: LIME }, line: { color: LIME }, objectName: `step ${n} badge` });
  T(s, n, { x, y: 2.35, w: 0.5, h: 0.5, fontFace: HEAD, fontSize: 18, bold: true, color: INK, align: "center", valign: "middle" });
  T(s, h, { x: x + 0.65, y: 2.3, w: 2.1, h: 0.6, fontFace: HEAD, fontSize: 15, bold: true, color: WHITE, valign: "middle" });
  T(s, t, { x, y: 3.05, w: 2.7, h: 0.9, fontSize: 12, color: "B9C4BE", valign: "top" });
});
T(s, "Caveat: the data is unusually uniform, which suggests a sampled or synthetic extract. The pipeline re-runs unchanged on production data to confirm.", { x: 0.6, y: 4.35, w: 8.0, h: 0.6, fontSize: 12, color: LIME, italic: true });
s.addImage({ path: LOGO_MARK, x: 8.75, y: 4.3, w: 0.65, h: 0.65, altText: "Ola Ride Insights logo mark" });
s.addNotes("Close on the decision: approve a pilot of re-dispatch on stalled pickups and a win-back flow, measured on driver-attributable failure rate. Be explicit about the data caveat and the plan to re-validate on production data.");

// ---------------------------------------------------------------- write + theme
(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
