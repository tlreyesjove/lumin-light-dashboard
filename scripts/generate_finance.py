"""
Generates the Finance tab: one row per (month, subsidiary).

Design notes:

- revenue and cogs are NOT independently invented — they're calculated
  directly from the Sales tab's Closed Won deals: revenue is the sum of
  deal_value for deals that closed in that month/subsidiary, and cogs is
  the sum of (quantity x unit_cost) for those same deals. That's what
  makes "Sales bookings" and "Finance revenue" actually reconcile — you
  can open both CSVs, filter Sales to Closed Won for a given month, and
  the totals will match Finance exactly (they're the same underlying
  numbers, just aggregated differently).

- Revenue growth vs. the prior period isn't a separate invented growth
  rate either — it falls out naturally from CLOSED_DEALS_CURRENT being a
  bigger number than CLOSED_DEALS_PRIOR in config.py.

- opex is the one line Sales data can't inform (there's no G&A/headcount
  data in this project), so it's still modeled as a % of revenue.

- cash_balance approximates a real working-capital effect: institutional
  buyers are slow payers, so this month's cash COLLECTED is modeled as
  last month's revenue (a one-month lag), while costs are paid the same
  month they're incurred. That's what produces occasional down months in
  cash even when EBIT is positive — a believable "burn" story instead of
  cash moving in lockstep with revenue.
"""

import datetime
import numpy as np
import pandas as pd

import config
from generate_sales import generate_sales_data

rng = np.random.default_rng(config.RANDOM_SEED)


def month_range(start, end):
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(datetime.date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def revenue_and_cogs_from_sales(sales_df):
    """Aggregate Closed Won deals into (month, subsidiary) revenue + cogs."""
    won = sales_df[sales_df.stage == "Closed Won"].copy()
    won["month"] = pd.to_datetime(won["actual_close_date"]).dt.strftime("%Y-%m")
    won["deal_cogs"] = won["quantity"] * won["unit_cost"]

    grouped = won.groupby(["month", "subsidiary"]).agg(
        revenue=("deal_value", "sum"),
        cogs=("deal_cogs", "sum"),
    ).reset_index()
    return grouped


def generate_finance_data(sales_df=None):
    if sales_df is None:
        sales_df = generate_sales_data()

    revenue_cogs = revenue_and_cogs_from_sales(sales_df)

    all_months = month_range(config.PRIOR_PERIOD_START, config.CURRENT_PERIOD_END)
    scaffold = pd.DataFrame(
        [(m.strftime("%Y-%m"), sub) for m in all_months for sub in config.SUBSIDIARIES],
        columns=["month", "subsidiary"],
    )

    df = scaffold.merge(revenue_cogs, on=["month", "subsidiary"], how="left")
    df["revenue"] = df["revenue"].fillna(0.0)
    df["cogs"] = df["cogs"].fillna(0.0)

    df["opex"] = (df["revenue"] * config.BLENDED_OPEX_PCT_OF_REVENUE * rng.uniform(0.9, 1.1, len(df))).round(2)
    df["ebit"] = (df["revenue"] - df["cogs"] - df["opex"]).round(2)
    df["budget_revenue"] = (df["revenue"] * (1 + rng.uniform(-config.BUDGET_VARIANCE_PCT, config.BUDGET_VARIANCE_PCT, len(df)))).round(2)
    df["budget_ebit"] = (df["ebit"] * (1 + rng.uniform(-config.BUDGET_VARIANCE_PCT, config.BUDGET_VARIANCE_PCT, len(df)))).round(2)

    df = df.sort_values(["subsidiary", "month"]).reset_index(drop=True)

    # Cash balance: collections lag revenue by one month (AR_LAG_DAYS ~ 1 month),
    # costs paid same month. Running balance per subsidiary, starting at
    # STARTING_CASH_BALANCE at the very first month in the dataset.
    cash_rows = []
    for subsidiary, group in df.groupby("subsidiary", sort=False):
        group = group.reset_index(drop=True)
        cash_collected = group["revenue"].shift(1).fillna(group["revenue"].iloc[0])
        cash_paid = group["cogs"] + group["opex"]
        net_cash_change = cash_collected - cash_paid
        cash_balance = config.STARTING_CASH_BALANCE + net_cash_change.cumsum()
        group["net_cash_change"] = net_cash_change.round(2)
        group["cash_balance"] = cash_balance.round(2)
        cash_rows.append(group)

    df = pd.concat(cash_rows, ignore_index=True)
    return df


if __name__ == "__main__":
    sales_df = generate_sales_data()
    df = generate_finance_data(sales_df)
    print(df.head(12).to_string())
    print(f"\n{len(df)} rows generated")

    current = df[df.month >= config.CURRENT_PERIOD_START.strftime("%Y-%m")]
    prior = df[df.month < config.CURRENT_PERIOD_START.strftime("%Y-%m")]
    for sub in config.SUBSIDIARIES:
        cur_rev = current[current.subsidiary == sub].revenue.sum()
        pri_rev = prior[prior.subsidiary == sub].revenue.sum()
        target = config.ANNUAL_REVENUE_TARGET[sub]
        growth = (cur_rev - pri_rev) / pri_rev
        print(f"{sub}: current ${cur_rev:,.0f} ({cur_rev/target:.1%} of ${target:,.0f} target), "
              f"prior ${pri_rev:,.0f}, growth {growth:+.1%}")
        print(f"  EBIT margin: {current[current.subsidiary == sub].ebit.sum() / cur_rev:.1%}")
    print(f"Ending cash balance (all subsidiaries): ${df.groupby('subsidiary').cash_balance.last().sum():,.0f}")

    # Sanity check: Finance revenue should exactly equal Sales Closed Won value
    won = sales_df[sales_df.stage == "Closed Won"]
    print(f"\nCheck — Sales Closed Won total: ${won.deal_value.sum():,.0f}")
    print(f"Check — Finance revenue total:   ${df.revenue.sum():,.0f}")
