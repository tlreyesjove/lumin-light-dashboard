"""
Generates the Finance tab: one row per (month, subsidiary).

Design notes:

- Each subsidiary's current-period revenue is forced to land close to its
  ANNUAL_REVENUE_TARGET (config.py), spread unevenly across 12 months
  (random monthly weights, not a flat 1/12 each) so the trend line looks
  like a real business, not a ruler-straight line. Prior-period revenue is
  a flat percentage smaller (PRIOR_PERIOD_REVENUE_FACTOR), which is what
  drives "revenue growth vs. prior period" on the dashboard.

- COGS uses the blended gross margin implied by the product mix in
  config.PRODUCTS (weighted by selection_weight) — so Finance and Sales
  agree on roughly the same margin story, just at different levels of
  detail (Finance: one blended number a month; Sales: real margin per deal).

- cash_balance approximates a real working-capital effect: institutional
  buyers are slow payers, so this month's cash COLLECTED is modeled as
  last month's revenue (a one-month lag), while costs are paid the same
  month they're incurred. That's what produces occasional down months in
  cash even when EBIT is positive — a believable "burn" story instead of
  cash moving in lockstep with revenue.
"""

import calendar
import datetime
import numpy as np
import pandas as pd

import config

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


def blended_gross_margin_pct():
    total_weight = sum(p["selection_weight"] for p in config.PRODUCTS.values())
    weighted_margin = sum(
        p["selection_weight"] * (1 - p["unit_cost"] / p["unit_price"])
        for p in config.PRODUCTS.values()
    )
    return weighted_margin / total_weight


def monthly_weights(n_months):
    # Random positive weights that sum to 1 -> uneven but plausible month split.
    raw = rng.uniform(0.7, 1.3, n_months)
    return raw / raw.sum()


def generate_finance_data():
    gross_margin_pct = blended_gross_margin_pct()

    current_months = month_range(config.CURRENT_PERIOD_START, config.CURRENT_PERIOD_END)
    prior_months = month_range(config.PRIOR_PERIOD_START, config.PRIOR_PERIOD_END)

    rows = []
    for subsidiary in config.SUBSIDIARIES:
        current_total = config.ANNUAL_REVENUE_TARGET[subsidiary] * rng.uniform(0.95, 1.05)
        prior_total = current_total * config.PRIOR_PERIOD_REVENUE_FACTOR

        for period_months, period_total in [(prior_months, prior_total), (current_months, current_total)]:
            weights = monthly_weights(len(period_months))
            for month_date, weight in zip(period_months, weights):
                revenue = round(period_total * weight, 2)
                cogs = round(revenue * (1 - gross_margin_pct) * rng.uniform(0.95, 1.05), 2)
                opex = round(revenue * config.BLENDED_OPEX_PCT_OF_REVENUE * rng.uniform(0.9, 1.1), 2)
                ebit = round(revenue - cogs - opex, 2)
                budget_revenue = round(revenue * (1 + rng.uniform(-config.BUDGET_VARIANCE_PCT, config.BUDGET_VARIANCE_PCT)), 2)
                budget_ebit = round(ebit * (1 + rng.uniform(-config.BUDGET_VARIANCE_PCT, config.BUDGET_VARIANCE_PCT)), 2)

                last_day = calendar.monthrange(month_date.year, month_date.month)[1]

                rows.append({
                    "month": month_date.strftime("%Y-%m"),
                    "subsidiary": subsidiary,
                    "revenue": revenue,
                    "cogs": cogs,
                    "opex": opex,
                    "ebit": ebit,
                    "budget_revenue": budget_revenue,
                    "budget_ebit": budget_ebit,
                    "days_in_month": last_day,
                })

    df = pd.DataFrame(rows)
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
    df = df.drop(columns=["days_in_month"])
    return df


if __name__ == "__main__":
    df = generate_finance_data()
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
