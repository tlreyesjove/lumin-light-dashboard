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
    finance_df = generate_finance_data()
    inventory_df = generate_inventory_data()

    sales_df.to_csv(os.path.join(DATA_DIR, "sales.csv"), index=False)
    finance_df.to_csv(os.path.join(DATA_DIR, "finance.csv"), index=False)
    inventory_df.to_csv(os.path.join(DATA_DIR, "inventory.csv"), index=False)

    print(f"sales.csv:     {len(sales_df)} rows")
    print(f"finance.csv:   {len(finance_df)} rows")
    print(f"inventory.csv: {len(inventory_df)} rows")
    print(f"\nWritten to {os.path.abspath(DATA_DIR)}")


if __name__ == "__main__":
    main()
