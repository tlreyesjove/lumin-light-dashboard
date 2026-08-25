"""
Generates the Inventory tab: one row per (product, warehouse).

Design notes:

- avg_monthly_demand_units and max_monthly_demand_units are calculated
  from the ACTUAL Closed Won deals in sales.csv over the current 12-month
  period (grouped by month, product, subsidiary) — not an independent
  estimate. Same reconciliation principle as the Finance fix: Inventory's
  idea of "demand" should be traceable back to Sales, not separately made up.
  Months with no closed deals for a product count as zero units that
  month (they still pull the average down — a real slow month would too).

- Safety stock and reorder point use Tatiana's formulas:

      Safety Stock  = (Max Monthly Demand x Max Lead Time)
                       - (Avg Monthly Demand x Avg Lead Time)
      Reorder Point = (Avg Monthly Demand x Avg Lead Time) + Safety Stock

  With AVG_LEAD_TIME_MONTHS = MAX_LEAD_TIME_MONTHS = 1 (config.py), this
  simplifies to Reorder Point = Max Monthly Demand — i.e. "always hold
  enough stock to cover the busiest month you've actually seen." The
  formula is still written out in full (not hardcoded to that
  simplification) so it keeps working correctly if avg/max lead time
  are ever set to different values.

- stock_on_hand is reorder_point x a random multiplier, deliberately
  skewed so most rows are comfortably stocked but a few sit below or
  near the reorder point. A dashboard where every metric is always "fine"
  isn't a useful demo — the reorder-alert feature needs some real alerts
  to show off.

- This script does NOT compute the pipeline-aware reorder alert itself
  (i.e. "flag as low even if stock looks OK, because a big near-certain
  deal is about to close"). That's Streamlit app logic (Phase 3) — it
  needs this Inventory tab AND the Sales tab's open pipeline together.
  This tab just provides the raw stock/threshold numbers.
"""

import datetime
import numpy as np
import pandas as pd

import config
from generate_sales import generate_sales_data

rng = np.random.default_rng(config.RANDOM_SEED + 1)

STOCK_LEVEL_BUCKETS = [
    # (probability, (low_multiplier, high_multiplier))
    (0.15, (0.40, 0.90)),   # below/near reorder point -> alert-worthy
    (0.25, (0.90, 1.30)),   # borderline
    (0.60, (1.30, 3.00)),   # healthy
]


def sample_stock_multiplier():
    roll = rng.random()
    cumulative = 0.0
    for prob, (low, high) in STOCK_LEVEL_BUCKETS:
        cumulative += prob
        if roll < cumulative:
            return rng.uniform(low, high)
    return rng.uniform(*STOCK_LEVEL_BUCKETS[-1][1])


def current_period_months():
    months = []
    y, m = config.CURRENT_PERIOD_START.year, config.CURRENT_PERIOD_START.month
    end_y, end_m = config.CURRENT_PERIOD_END.year, config.CURRENT_PERIOD_END.month
    while (y, m) <= (end_y, end_m):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def monthly_demand_stats(sales_df):
    """Returns {(subsidiary, product): {'avg': x, 'max': y}} units/month,
    over the current 12-month period, from actual Closed Won deals."""
    months = current_period_months()

    won = sales_df[sales_df.status == "Won"].copy()
    won["month"] = pd.to_datetime(won["actual_close_date"]).dt.strftime("%Y-%m")
    won = won[won["month"].isin(months)]

    grouped = won.groupby(["subsidiary", "product", "month"])["quantity"].sum()

    stats = {}
    for subsidiary in config.SUBSIDIARIES:
        for product in config.PRODUCTS:
            monthly_units = [grouped.get((subsidiary, product, m), 0) for m in months]
            stats[(subsidiary, product)] = {
                "avg": sum(monthly_units) / len(months),
                "max": max(monthly_units),
            }
    return stats


def generate_inventory_data(sales_df=None):
    if sales_df is None:
        sales_df = generate_sales_data()

    demand_stats = monthly_demand_stats(sales_df)

    rows = []
    for subsidiary in config.SUBSIDIARIES:
        warehouse = config.WAREHOUSES[subsidiary]["warehouse"]
        for product in config.PRODUCTS:
            avg_monthly_demand = demand_stats[(subsidiary, product)]["avg"]
            max_monthly_demand = demand_stats[(subsidiary, product)]["max"]

            safety_stock = (max_monthly_demand * config.MAX_LEAD_TIME_MONTHS) - \
                            (avg_monthly_demand * config.AVG_LEAD_TIME_MONTHS)
            safety_stock = max(0.0, safety_stock)  # can't hold negative safety stock
            reorder_point = (avg_monthly_demand * config.AVG_LEAD_TIME_MONTHS) + safety_stock

            reorder_point = round(reorder_point)
            stock_on_hand = round(reorder_point * sample_stock_multiplier())

            rows.append({
                "warehouse": warehouse,
                "subsidiary": subsidiary,
                "product": product,
                "stock_on_hand": stock_on_hand,
                "avg_monthly_demand_units": round(avg_monthly_demand, 1),
                "max_monthly_demand_units": round(max_monthly_demand, 1),
                "safety_stock": round(safety_stock),
                "reorder_point": reorder_point,
                "as_of_date": config.TODAY.isoformat(),
            })

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    sales_df = generate_sales_data()
    df = generate_inventory_data(sales_df)
    print(df.to_string())
    below = df[df.stock_on_hand < df.reorder_point]
    print(f"\n{len(below)} of {len(df)} rows below reorder point")
