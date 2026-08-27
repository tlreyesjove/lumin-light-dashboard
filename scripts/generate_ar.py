"""
Generates the AR tab: one invoice per Closed Won deal.

This is the single source of truth behind three things on the redone
Finance tab that the Sales/Finance tabs' existing monthly data can't
answer on its own:

- Recognized Revenue (Finance tab) — summed by invoice ISSUE month, not
  by deal close month. See config.py's AR section for why that's the
  whole point of this file existing.
- DSO and AR Overdue $ (Cash & Risk tiles) — both need actual payment
  timing per invoice, which a monthly-aggregate table can't provide.
- AR Aging Detail (the tab's detail table) — needs invoice-level rows.

Design notes:

- issue_date = actual_close_date + a short random lag (delivery/invoicing
  turnaround, config.INVOICE_LAG_DAYS_RANGE) — NOT a separate collection
  lag. due_date is issue_date + PAYMENT_TERMS_DAYS (net-30 for everyone).
- Whether an invoice is paid, and when, depends on how long the customer
  actually takes from issue_date (config.PAYMENT_LAG_DAYS, by client_type
  — institutional buyers draw from a slower distribution, same "slow
  payer" story AR_LAG_DAYS already tells elsewhere in this model). If
  that payment date hasn't arrived yet as of TODAY, the invoice is still
  outstanding — Overdue if past its due_date, Current if not.
- Every invoice's numbers (issue/due/paid dates, amount) are fixed at
  generation time, same as everything else in this pipeline — status and
  days_overdue are the only two fields that depend on "today" and would
  need to be recomputed if this were regenerated on a different date.
"""

import numpy as np
import pandas as pd

import config
from generate_sales import generate_sales_data

rng = np.random.default_rng(config.RANDOM_SEED)


def generate_ar_data(sales_df=None):
    if sales_df is None:
        sales_df = generate_sales_data()

    won = sales_df[sales_df.status == "Won"].copy().reset_index(drop=True)
    n = len(won)

    invoice_lag_days = rng.integers(config.INVOICE_LAG_DAYS_RANGE[0], config.INVOICE_LAG_DAYS_RANGE[1] + 1, n)
    issue_date = pd.to_datetime(won["actual_close_date"]) + pd.to_timedelta(invoice_lag_days, unit="D")
    due_date = issue_date + pd.to_timedelta(config.PAYMENT_TERMS_DAYS, unit="D")

    payment_lag_days = np.empty(n)
    for client_type, (mean, std) in config.PAYMENT_LAG_DAYS.items():
        mask = (won["client_type"] == client_type).to_numpy()
        payment_lag_days[mask] = np.clip(rng.normal(mean, std, mask.sum()), 5, None)
    paid_date = issue_date + pd.to_timedelta(payment_lag_days.round(), unit="D")

    today = pd.Timestamp(config.TODAY)
    is_paid = paid_date <= today
    status = np.where(is_paid, "Paid", np.where(due_date < today, "Overdue", "Current"))
    days_overdue = np.where(status == "Overdue", (today - due_date).dt.days, 0)

    ar = pd.DataFrame({
        "invoice_id": [f"INV-{i + 1:04d}" for i in range(n)],
        "deal_id": won["deal_id"],
        "subsidiary": won["subsidiary"],
        "buyer_type": won["buyer_type"],
        "client_type": won["client_type"],
        "buyer_name": won["buyer_name"],
        "product": won["product"],
        "amount": won["deal_value"],
        # Carried straight from the deal — this is what lets "Recognized
        # Revenue" be scoped to the SAME cohort of deals as "Booked"
        # (same year/quarter the deal actually closed), rather than
        # whatever calendar period the invoice happens to land in. Using
        # issue_date's own calendar year for that instead pulls in
        # invoices for deals that closed in the PRIOR year (issued a few
        # weeks into the new year) — inflating "this year's" recognized
        # revenue with deals that were never part of this year's bookings,
        # which can flip the sign of the whole comparison the wrong way.
        "actual_close_date": won["actual_close_date"],
        "issue_date": issue_date,
        "due_date": due_date,
        "paid_date": paid_date.where(is_paid),
        "status": status,
        "days_overdue": days_overdue,
    })
    return ar.sort_values("issue_date").reset_index(drop=True)


if __name__ == "__main__":
    sales_df = generate_sales_data()
    ar_df = generate_ar_data(sales_df)
    print(ar_df.head(10).to_string())
    print(f"\n{len(ar_df)} invoices generated")
    print(ar_df.status.value_counts())

    print(f"\nCheck — invoice total: ${ar_df.amount.sum():,.0f}")
    won_total = sales_df[sales_df.status == 'Won'].deal_value.sum()
    print(f"Check — Sales Closed Won total: ${won_total:,.0f}")
    assert abs(ar_df.amount.sum() - won_total) < 1.0, "AR and Sales Closed Won totals don't match!"
    print("Match confirmed (every Won deal has exactly one invoice for its full value).")

    paid = ar_df[ar_df.status == "Paid"]
    dso = (paid.paid_date - paid.issue_date).dt.days.mean()
    print(f"\nDSO (all paid invoices): {dso:.0f} days")
    overdue_amt = ar_df[ar_df.status == "Overdue"].amount.sum()
    print(f"AR Overdue: ${overdue_amt:,.0f} across {(ar_df.status == 'Overdue').sum()} invoices")
