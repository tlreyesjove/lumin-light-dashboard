"""
Runs all three generators and writes their output to /data as CSVs.

Usage:
    python3 generate_data.py

Re-run any time you change an assumption in config.py — it always
overwrites the same three files, so there's nothing to clean up first.
"""

import os

from generate_sales import generate_sales_data
from generate_finance import generate_finance_data
from generate_inventory import generate_inventory_data

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    sales_df = generate_sales_data()
    finance_df = generate_finance_data(sales_df)  # derived from sales_df, not independent
    inventory_df = generate_inventory_data()

    sales_df.to_csv(os.path.join(DATA_DIR, "sales.csv"), index=False)
    finance_df.to_csv(os.path.join(DATA_DIR, "finance.csv"), index=False)
    inventory_df.to_csv(os.path.join(DATA_DIR, "inventory.csv"), index=False)

    print(f"sales.csv:     {len(sales_df)} rows")
    print(f"finance.csv:   {len(finance_df)} rows")
    print(f"inventory.csv: {len(inventory_df)} rows")
    print(f"\nWritten to {os.path.abspath(DATA_DIR)}")

    won_total = sales_df[sales_df.stage == "Closed Won"].deal_value.sum()
    revenue_total = finance_df.revenue.sum()
    print(f"\nReconciliation check: Sales Closed Won ${won_total:,.0f} vs. Finance revenue ${revenue_total:,.0f}")
    assert abs(won_total - revenue_total) < 1.0, "Sales and Finance totals don't match!"
    print("Match confirmed.")


if __name__ == "__main__":
    main()
