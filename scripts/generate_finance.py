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

- opex is built from the SAME cost structure as the financial model's
  budget (fixed costs — salaries, rent, etc. — spread flat across months,
  plus commission that scales with actual revenue), with modest random
  noise layered on top for normal month-to-month execution variance.
  Actual and Budget sharing a cost structure is what makes "actual vs.
  budget" a meaningful comparison — if Actual used an unrelated flat-%-
  of-revenue guess instead, any variance would just reflect the two
  numbers being built two different ways, not a real business story.

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
    won = sales_df[sales_df.status == "Won"].copy()
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

    # Stop at TODAY, not CURRENT_PERIOD_END (Dec 31) — months that haven't
    # happened yet shouldn't show up as rows of $0 revenue.
    all_months = month_range(config.PRIOR_PERIOD_START, config.TODAY)
    scaffold = pd.DataFrame(
        [(m.strftime("%Y-%m"), sub) for m in all_months for sub in config.SUBSIDIARIES],
        columns=["month", "subsidiary"],
    )

    df = scaffold.merge(revenue_cogs, on=["month", "subsidiary"], how="left")
    df["revenue"] = df["revenue"].fillna(0.0)
    df["cogs"] = df["cogs"].fillna(0.0)

    cost = config.read_cost_structure()
    df["year"] = df["month"].str[:4].astype(int)

    def monthly_opex(row):
        sub, year, revenue = row["subsidiary"], row["year"], row["revenue"]
        salaries = cost["headcount_base"][sub][year] * (1 + cost["benefits_loading"]) / 12
        commission = revenue * cost["commission_pct"]
        other_annual = cost["other_opex_2025_annual"][sub]
        if year == 2026:
            other_annual *= (1 + cost["inflation"])
        other = other_annual / 12
        return salaries, commission, other

    salaries_col, commission_col, other_col = zip(*df.apply(monthly_opex, axis=1))
    noise = rng.uniform(0.92, 1.08, len(df))  # normal month-to-month execution variance
    df["opex"] = ((pd.Series(salaries_col) + pd.Series(other_col)) * noise + pd.Series(commission_col)).round(2)

    da_monthly = df.apply(lambda r: cost["da"][r["subsidiary"]] / 12, axis=1)
    df["ebit"] = (df["revenue"] - df["cogs"] - df["opex"] - da_monthly).round(2)
    df = df.drop(columns=["year"])

    # budget_revenue/budget_ebit are the real monthly plan from the financial
    # model — not noise layered on top of actuals. A genuine budget is set
    # before the year starts and doesn't move just because actuals came in
    # differently, which is exactly what makes "actual vs. budget" meaningful.
    monthly_budget = config.read_monthly_budget()
    df["budget_revenue"] = df.apply(lambda r: monthly_budget[(r["subsidiary"], r["month"])]["budget_revenue"], axis=1)
    df["budget_ebit"] = df.apply(lambda r: monthly_budget[(r["subsidiary"], r["month"])]["budget_ebit"], axis=1)

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

    # YTD vs. YTD: compare Jan-through-TODAY's-month in both years, not
    # 8 months of this year against a full 12 months of last year.
    current = df[df.month >= config.CURRENT_PERIOD_START.strftime("%Y-%m")]
    prior_ytd_cutoff = f"{config.PRIOR_PERIOD_START.year}-{config.TODAY.month:02d}"
    prior = df[(df.month >= config.PRIOR_PERIOD_START.strftime("%Y-%m")) & (df.month <= prior_ytd_cutoff)]
    annual_budget = config.read_annual_budget()
    for sub in config.SUBSIDIARIES:
        cur_rev = current[current.subsidiary == sub].revenue.sum()
        pri_rev = prior[prior.subsidiary == sub].revenue.sum()
        target = config.ANNUAL_REVENUE_TARGET[sub]
        ytd_target = target * ((config.TODAY - config.CURRENT_PERIOD_START).days / (config.CURRENT_PERIOD_END - config.CURRENT_PERIOD_START).days)
        growth = (cur_rev - pri_rev) / pri_rev
        print(f"{sub}: YTD ${cur_rev:,.0f} ({cur_rev/ytd_target:.1%} of ${ytd_target:,.0f} prorated YTD target, "
              f"{cur_rev/target:.1%} of ${target:,.0f} full-year target), "
              f"same period last year ${pri_rev:,.0f}, YoY growth {growth:+.1%}")
        print(f"  EBIT margin: {current[current.subsidiary == sub].ebit.sum() / cur_rev:.1%}")

        # EBIT is compared against the FULL fiscal year's budget, not a
        # prorated slice — see config.read_annual_budget's docstring for why.
        cur_ebit = current[current.subsidiary == sub].ebit.sum()
        full_year_ebit_budget = annual_budget[(sub, 2026)]["ebit"]
        print(f"  EBIT: ${cur_ebit:,.0f} YTD vs. ${full_year_ebit_budget:,.0f} full-year budget "
              f"({cur_ebit/full_year_ebit_budget:.1%})")
    print(f"Ending cash balance (all subsidiaries): ${df.groupby('subsidiary').cash_balance.last().sum():,.0f}")

    # Sanity check: Finance revenue should exactly equal Sales Closed Won value
    won = sales_df[sales_df.status == "Won"]
    print(f"\nCheck — Sales Closed Won total: ${won.deal_value.sum():,.0f}")
    print(f"Check — Finance revenue total:   ${df.revenue.sum():,.0f}")
