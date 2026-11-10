# Power BI Build Guide - Ola Ride Insights

A page-by-page recipe for the five dashboard views and ten visuals required by the project brief.
Expect about **60-90 minutes**. Everything you need is in this folder:

| File | Purpose |
|---|---|
| `OLA_Theme.json` | Brand colours, fonts, card/page styling (View → Themes → Browse for themes) |
| `power_query.m` | Load + clean the data (Option A: cleaned CSV; Option B: original workbook) |
| `measures.dax` | Every measure and the date table, with the **expected value** in a comment |
| `../data/ola_rides_clean.csv.gz` | The cleaned dataset (identical to the SQL table and the Streamlit app) |

> **Why this is a guide and not a `.pbix`:** `.pbix` is a proprietary binary that only Power BI Desktop can write.
> The Streamlit app reproduces all ten visuals (and more), so you always have a working dashboard; use this
> guide to build the Power BI version in your own Desktop and, optionally, embed it back into Streamlit.

---

## 1. Load the data

**Option A - cleaned data (recommended).** Home → Get data → Blank query → Advanced editor → paste *Option A* from
`power_query.m` → fix the file path → Close & Apply.
**Option B - from MySQL.** Run `sql/ola_schema_and_cleaning.sql`, then Get data → MySQL database → import
`ola_rides`, `dim_vehicle`, `dim_payment` (use the *Connect MySQL to Power BI* link in the brief for the connector).
**Option C - original workbook.** Use *Option B* in `power_query.m`; it repeats the same cleaning steps.

Name the main table **`ola_rides`** (the DAX assumes this name).

## 2. Model

1. Modeling → New table → paste `DimDate` from `measures.dax`.
2. Relationship: `DimDate[Date]` (one) → `ola_rides[Date]` (many), single direction.
3. If you imported the dimension tables: `dim_vehicle[Vehicle_Type]` → `ola_rides[Vehicle_Type]`, `dim_payment[Payment_Method]` → `ola_rides[Payment_Method]`.
4. Create a blank table `_Measures` and paste every measure from `measures.dax`.
5. Mark **Booking_Status** sort order: Success, Canceled by Customer, Canceled by Driver, Driver Not Found.
6. Set format: `Success Rate %` etc. → Percentage (1 decimal); `Revenue` → Currency ₹ with 0 decimals, display unit Millions.

## 3. Apply the theme and page setup

View → Themes → Browse for themes → `OLA_Theme.json`. Page size 16:9. Add the logo
(`assets/logo_full.png`) top-left of every page and a page title text box that states the **finding**, not the topic
(examples are given for every page below).

**Global slicers (sync across all pages - View → Sync slicers):**
`Date` (between), `Vehicle_Type` (dropdown), `Time_Band` (tile), `Is_Weekend` (toggle: Weekdays/Weekends), `Pickup_Location` (dropdown, searchable).

**Verification card strip** (put on Overall, then hide or keep): `Total Bookings` = **103,024**, `Success Rate %` = **62.1%**,
`Revenue` = **₹35.08 M**. If these do not match, the data load or a filter is wrong.

---

## 4. Pages and visuals

### Page 1 - Overall
Title text: **"Demand is steady at ~3,300 bookings a day, but only 62% convert into rides"**

| Brief question | Visual | Fields | Notes |
|---|---|---|---|
| KPI strip | 5 × Card | `Total Bookings`, `Success Rate %`, `Revenue`, `Quoted Fare Lost`, `Avg Distance (Completed km)` | Card callout font 28 |
| **1. Ride Volume Over Time** | Line and clustered column chart | Axis `DimDate[Date]`; Columns `Total Bookings`; Line `Bookings 7d Avg` | Add *Average line* (Analytics pane) = 3,323; annotate peak (30 Jul) with a text box |
| **2. Booking Status Breakdown** | Donut | Legend `Booking_Status`; Values `Total Bookings` | Data labels: percentage + value; colours Success `#1F9D6B`, Customer `#F2A93B`, Driver `#E4572E`, Not found `#6B7A99` |
| Insight text box | Text | - | "Driver-side failures are 27.7% of bookings vs 10.2% customer cancels" |

### Page 2 - Vehicle Type
Title text: **"Vehicle choice does not change outcomes - every type fails about 38% of the time"**

| Brief question | Visual | Fields | Notes |
|---|---|---|---|
| **3. Top 5 Vehicle Types by Ride Distance** | Clustered bar | Axis `Vehicle_Type`; Values `Total Distance (Completed km)` | Filter pane: Top N = 5 by `Total Distance (Completed km)`; sort descending; data labels on |
| **4. Average Customer Ratings by Vehicle Type** | Clustered column | Axis `Vehicle_Type`; Values `Avg Customer Rating` | Y axis 0-5 (do not truncate); constant line at 4.0 |
| Outcome mix | 100% stacked bar | Axis `Vehicle_Type`; Legend `Booking_Status`; Values `Total Bookings` | Shows the identical mix |
| Fare per km | Column | Axis `Vehicle_Type`; Values `Fare per km` | Annotate Auto = 2.5× the others |

### Page 3 - Revenue
Title text: **"Cash still carries 55% of revenue, and no customer matters individually"**

| Brief question | Visual | Fields | Notes |
|---|---|---|---|
| **6. Revenue by Payment Method** | Clustered column or donut | Axis `Payment_Method`; Values `Revenue` | Show value and % of total |
| **7. Top 5 Customers by Total Booking Value** | Bar + table | `Customer_ID`; `Revenue` | Filter pane Top N = 5 by `Revenue`; add `Share` = `DIVIDE([Revenue], CALCULATE([Revenue], ALL(ola_rides)))` |
| **8. Ride Distance Distribution Per Day** | Line chart with min/max/median **or** Box and whisker (AppSource custom visual) | Axis `DimDate[Date]`; Values: Min, Median, Max of `Ride_Distance` (Is_Successful = 1 filter) | Default option needs no add-in: line chart with *Average*, *Min*, *Max* of `Ride_Distance` filtered to `Booking_Status = Success` |
| Revenue leakage | Waterfall | Category `Failure_Type`; Y `Quoted Fare Lost` | Add `Revenue` as the last bar |

### Page 4 - Cancellation
Title text: **"88% of failures trace back to drivers - and customers cancel because of them"**

| Brief question | Visual | Fields | Notes |
|---|---|---|---|
| **5a. Cancelled Rides Reasons (Customer)** | Bar chart (horizontal) | Axis `Canceled_Rides_by_Customer`; Values `Total Bookings`; visual filter `Booking_Status = Canceled by Customer` | Conditional colour: *Driver is not moving…* and *Driver asked to cancel* = `#E4572E`, others `#F2A93B` |
| **5b. Cancelled Rides Reasons (Drivers)** | Bar chart (horizontal) | Axis `Canceled_Rides_by_Driver`; Values `Total Bookings`; filter `Booking_Status = Canceled by Driver` | Highlight *Personal & Car related issue* |
| Incomplete rides | Donut | Legend `Incomplete_Rides_Reason`; Values `Incomplete Rides` | 3,926 rides, ₹2.25 M at risk |
| Integrity flag | Card | `AC Complaint on Non-AC Vehicle` | 686 - AC complaints on Bike/eBike/Auto |

### Page 5 - Ratings
Title text: **"Ratings are evenly spread from 3.0 to 5.0 and unrelated to service - they cannot guide incentives"**

| Brief question | Visual | Fields | Notes |
|---|---|---|---|
| **9a. Driver Ratings Distribution** | Column chart | Axis `Driver_Ratings` (bin size 0.5 or use value); Values `Total Bookings` (filter Is_Successful = 1) | Add average line = 4.00 |
| **9b. Customer Ratings** | Column chart | Axis `Customer_Rating`; same | - |
| **10. Customer vs. Driver Ratings** | Matrix (heat-map) or scatter | Rows binned `Driver_Ratings`; Columns binned `Customer_Rating`; Values `Total Bookings` | Conditional formatting → background colour scale; shows no diagonal |

---

## 5. Interactivity checklist (evaluation: "interactive and user-friendly")

- [ ] Synced slicers on every page (Date, Vehicle, Time band, Weekday/Weekend, Pickup area).
- [ ] **Drill-through** page from any `Vehicle_Type` visual to a booking-level table (`Booking_ID`, `Customer_ID`, `Booking_Status`, `Booking_Value`).
- [ ] **Tooltips**: report-page tooltip showing Bookings, Success %, Revenue for hovered category.
- [ ] **Bookmarks + buttons**: "Completed only" / "All bookings" toggle (Page 1).
- [ ] **Navigator**: Insert → Buttons → Navigator → Page navigator.
- [ ] Alt-text on every visual; tab order set; colour is never the only signal.

## 6. Publish and embed in Streamlit (optional)

1. Home → Publish → choose a workspace.
2. On the service: File → Embed report → **Publish to web (public)** → copy the link. *This makes the report public; only use it for non-sensitive data like this sample.*
3. Put the link in `.streamlit/secrets.toml` as `POWERBI_EMBED_URL = "..."` (see `secrets.toml.example`).
4. The **Power BI** page of the Streamlit app will now embed the live report.

## 7. Common pitfalls

| Symptom | Cause / fix |
|---|---|
| Revenue looks too high | You summed `Booking_Value` without the `Success` filter (failed bookings carry a *quoted* fare). Use the `Revenue` measure. |
| Average distance ≈ 14 km instead of 22.9 | Cancelled bookings have 0 km. Use `Avg Distance (Completed km)`; the "(All Bookings)" measure matches the workbook's AVERAGEIF. |
| Weekday chart shows Mon-Wed as busier | Calendar artefact: July 2024 has five of each. Use `Avg Bookings per Day`. |
| Ratings average shows blank for cancelled rides | Expected: ratings exist only for completed rides (structural nulls). Do not replace nulls with 0. |
| `Date` shows as text | Set the column type to *Date* in Power Query (Option A does this). |
