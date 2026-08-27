"""
Runs all four generators and writes their output to /data as CSVs.

Usage:
    python3 generate_data.py

Re-run any time you change an assumption in config.py — it always
overwrites the same four files, so there's nothing to clean up first.
"""

import os

from generate_sales import generate_sales_data
from generate_finance import generate_finance_data
from generate_inventory import generate_inventory_data
from generate_ar import generate_ar_data

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    sales_df = generate_sales_data()
    finance_df = generate_finance_data(sales_df)      # derived from sales_df, not independent
    inventory_df = generate_inventory_data(sales_df)  # demand stats derived from sales_df too
    ar_df = generate_ar_data(sales_df)                # one invoice per Closed Won deal

    sales_df.to_csv(os.path.join(DATA_DIR, "sales.csv"), index=False)
    finance_df.to_csv(os.path.join(DATA_DIR, "finance.csv"), index=False)
    inventory_df.to_csv(os.path.join(DATA_DIR, "inventory.csv"), index=False)
    ar_df.to_csv(os.path.join(DATA_DIR, "ar.csv"), index=False)

    print(f"sales.csv:     {len(sales_df)} rows")
    print(f"finance.csv:   {len(finance_df)} rows")
    print(f"inventory.csv: {len(inventory_df)} rows")
    print(f"ar.csv:        {len(ar_df)} rows")
    print(f"\nWritten to {os.path.abspath(DATA_DIR)}")

    won_total = sales_df[sales_df.status == "Won"].deal_value.sum()
    revenue_total = finance_df.revenue.sum()
    ar_total = ar_df.amount.sum()
    print(f"\nReconciliation check: Sales Closed Won ${won_total:,.0f} vs. Finance revenue ${revenue_total:,.0f} "
          f"vs. AR invoiced ${ar_total:,.0f}")
    assert abs(won_total - revenue_total) < 1.0, "Sales and Finance totals don't match!"
    assert abs(won_total - ar_total) < 1.0, "Sales and AR totals don't match!"
    print("Match confirmed.")


if __name__ == "__main__":
    main()
