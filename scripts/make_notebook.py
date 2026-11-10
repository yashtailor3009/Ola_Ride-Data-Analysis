"""
scripts/make_notebook.py - writes notebooks/01_EDA.ipynb (nbformat 4, no outputs).
Run:  python scripts/make_notebook.py      Open the notebook with Jupyter / VS Code and 'Run All'.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "notebooks" / "01_EDA.ipynb"
cells = []
md = lambda s: cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)})   # noqa: E731
code = lambda s: cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],        # noqa: E731
                               "source": s.strip("\n").splitlines(True)})

md("""
# Ola Ride Insights - Exploratory Data Analysis
**Goal:** understand the July 2024 booking data before modelling or dashboarding: structure, quality, distributions,
relationships and the questions worth asking.
Run from the `notebooks/` folder. The cleaned data comes from `python -m ola.preprocessing --raw OLA_DataSet.xlsx`.
""")
code("""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))          # make the `ola` package importable

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

from ola import config as cfg
from ola.data import load_clean

sns.set_theme(style="whitegrid", rc={"axes.edgecolor": cfg.GRID, "axes.titleweight": "bold"})
df = load_clean()
done = df[df.Is_Successful == 1]
print(df.shape)
""")
md("## 1. Structure and types")
code("""
display(df.head(3).T)
df.dtypes.value_counts()
""")
md("""
## 2. Missing values - are they errors or by design?
The raw sheet used the text `'null'`. The table below shows *where* the nulls are, by booking status:
every null is **structural** (e.g. no rating on a cancelled ride), so we must not impute them.
""")
code("""
nulls = df.groupby("Booking_Status")[["Payment_Method", "Driver_Ratings", "Customer_Rating", "V_TAT",
                                      "Canceled_Rides_by_Customer", "Canceled_Rides_by_Driver",
                                      "Incomplete_Rides"]].apply(lambda g: g.isna().mean().round(2))
nulls
""")
md("## 3. The target: how do bookings end?")
code("""
order = cfg.STATUS_ORDER
ax = sns.countplot(data=df, y="Booking_Status", order=order, hue="Booking_Status", hue_order=order,
                   palette=cfg.STATUS_COLORS, legend=False)
for c in ax.containers:
    ax.bar_label(c, fmt="{:,.0f}", padding=3)
ax.set_title("Only 62% of bookings are completed"); ax.set_xlabel("Bookings"); ax.set_ylabel("")
plt.show()
""")
md("## 4. Distributions")
code("""
fig, axes = plt.subplots(1, 3, figsize=(15, 3.6))
sns.histplot(done.Booking_Value, bins=40, ax=axes[0], color=cfg.INK); axes[0].set_title("Fare (completed rides)")
sns.histplot(done.Ride_Distance, bins=25, ax=axes[1], color=cfg.INK); axes[1].set_title("Distance (completed rides)")
sns.histplot(done.Customer_Rating, bins=21, ax=axes[2], color=cfg.INK); axes[2].set_title("Customer rating")
plt.tight_layout(); plt.show()
print("Fare skew:", round(done.Booking_Value.skew(), 2), "| rating min/max:", done.Customer_Rating.min(), done.Customer_Rating.max())
""")
md("**Reading:** fares are right-skewed; distance and ratings are flat (uniform-looking). Ratings never go below 3.0.")
md("## 5. Time patterns - and a calendar trap")
code("""
daily = df.groupby("Date").size()
hourly = df.groupby("Ride_Hour").size()
wd = df.groupby("Day_Name").agg(total=("Booking_ID", "size"), days=("Date", "nunique")).reindex(cfg.WEEKDAY_ORDER)
wd["per_day"] = wd.total / wd.days

fig, axes = plt.subplots(1, 3, figsize=(16, 3.8))
daily.plot(ax=axes[0], color=cfg.INK); axes[0].set_title("Bookings per day"); axes[0].set_ylim(0)
hourly.plot.bar(ax=axes[1], color=cfg.INK); axes[1].set_title("Bookings per hour")
wd[["total", "per_day"]].assign(per_day=wd.per_day * 4).plot.bar(ax=axes[2], color=["#C9D2CC", cfg.INK])
axes[2].set_title("Weekday: raw total vs per-day (x4 for scale)")
plt.tight_layout(); plt.show()
wd
""")
md("""
**Trap avoided:** Mon-Wed look ~25% busier, but July 2024 had **five** Mon/Tue/Wed and **four** of the other weekdays.
Per-day averages are flat. Always normalise by the number of calendar days.
""")
code("""
print("Hourly uniformity (chi-square) p =", round(stats.chisquare(hourly).pvalue, 3))
""")
md("## 6. Relationships")
code("""
corr = done[["Booking_Value", "Ride_Distance", "V_TAT", "C_TAT", "Driver_Ratings", "Customer_Rating"]].corr()
sns.heatmap(corr, annot=True, fmt=".3f", cmap="Greens", vmin=-1, vmax=1); plt.title("Correlations (completed rides)"); plt.show()
""")
md("**Surprise:** fare vs distance correlation is ~0 and ratings correlate with nothing - unusual for real ride data.")
code("""
sample = done.sample(4000, random_state=1)
sns.scatterplot(data=sample, x="Ride_Distance", y="Booking_Value", alpha=0.25, color=cfg.INK)
plt.title(f"Fare vs distance (r = {done.Booking_Value.corr(done.Ride_Distance):.3f})"); plt.show()
""")
md("## 7. Is a difference real? Success rate by segment")
code("""
for col in ["Vehicle_Type", "Ride_Hour", "Day_Name", "Pickup_Location"]:
    p = stats.chi2_contingency(pd.crosstab(df[col], df.Booking_Status))[1]
    rate = df.groupby(col).Is_Successful.mean() * 100
    print(f"{col:16s} success {rate.min():.1f}%-{rate.max():.1f}%   chi-square p = {p:.3f}")
""")
md("**Reading:** none of the segment gaps is significant, so the 38% failure rate is a *platform-wide* property.")
md("## 8. Why do bookings fail?")
code("""
fig, axes = plt.subplots(1, 2, figsize=(15, 3.8))
df.Canceled_Rides_by_Customer.value_counts().sort_values().plot.barh(ax=axes[0], color=cfg.STATUS_COLORS["Canceled by Customer"])
axes[0].set_title("Customer cancellation reasons")
df.Canceled_Rides_by_Driver.value_counts().sort_values().plot.barh(ax=axes[1], color=cfg.STATUS_COLORS["Canceled by Driver"])
axes[1].set_title("Driver cancellation reasons")
plt.tight_layout(); plt.show()
""")
md("## 9. Outliers")
code("""
q1, q3 = done.Booking_Value.quantile([.25, .75]); iqr = q3 - q1
print("Fare IQR upper fence:", q3 + 1.5 * iqr, "| rides above it:", int((done.Booking_Value > q3 + 1.5 * iqr).sum()))
print("Fare per km > 500:", int((done.Fare_Per_Km > cfg.EXTREME_FARE_PER_KM).sum()))
print("Pickup == drop:", int(df.Is_Same_Pickup_Drop.sum()))
""")
md("## 10. Customers")
code("""
per = df.groupby("Customer_ID").agg(n=("Booking_ID", "size"), ok=("Is_Successful", "sum"))
print(per.n.value_counts().sort_index().to_string())
print("Never completed a ride:", f"{(per.ok == 0).mean():.1%}")
""")
md("""
## Findings to carry into SQL, Power BI and Streamlit
1. 38% of bookings fail, uniformly across every segment (systemic).
2. Driver-side causes dominate the failures.
3. Demand has no hourly peak; the weekday pattern is a calendar artefact.
4. Fare is unrelated to distance; ratings are unrelated to everything.
5. 36.6% of customers never completed a ride; 91.6% booked once.
6. The data is unusually uniform - validate on production data before operational decisions.
""")

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                   "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(nb, indent=1))
print("wrote", OUT, len(cells), "cells")
