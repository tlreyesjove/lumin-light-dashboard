"""
Generates the Inventory tab: one row per (product, warehouse).

Design notes:

- reorder_point is a static safety-stock threshold: expected daily unit
  demand for that product/subsidiary x REORDER_DAYS_OF_COVER. Expected
  demand comes from the same assumptions used in generate_sales.py
  (revenue target x product selection_weight, divided by unit price) —
  so Inventory and Sales are built from the same underlying story rather
  than being independently made up.

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

import numpy as np
import pandas as pd

import config

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


def generate_inventory_data():
    period_days = (config.CURRENT_PERIOD_END - config.CURRENT_PERIOD_START).days + 1

    rows = []
    for subsidiary in config.SUBSIDIARIES:
        warehouse = config.WAREHOUSES[subsidiary]["warehouse"]
        for product, spec in config.PRODUCTS.items():
            expected_annual_revenue = config.ANNUAL_REVENUE_TARGET[subsidiary] * spec["selection_weight"]
            expected_annual_units = expected_annual_revenue / spec["unit_price"]
            daily_demand_units = expected_annual_units / period_days

            reorder_point = round(daily_demand_units * config.REORDER_DAYS_OF_COVER)
            stock_on_hand = round(reorder_point * sample_stock_multiplier())

            rows.append({
                "warehouse": warehouse,
                "subsidiary": subsidiary,
                "product": product,
                "stock_on_hand": stock_on_hand,
                "reorder_point": reorder_point,
                "avg_daily_demand_units": round(daily_demand_units, 1),
                "as_of_date": config.TODAY.isoformat(),
            })

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    df = generate_inventory_data()
    print(df.to_string())
    below = df[df.stock_on_hand < df.reorder_point]
    print(f"\n{len(below)} of {len(df)} rows below static reorder point")
