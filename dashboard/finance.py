"""
Finance pillar: revenue (total + by subsidiary), YoY growth, margin by
product, EBIT vs budget, cash position & burn rate, budget vs actual.

Two framing decisions carried over from building the data pipeline itself
(see Learning Doc 2.1 and 2.4) — repeated here because getting them wrong
would silently mislead a reader, not just look slightly off:

- Revenue growth compares YTD to the SAME YTD months last year, not YTD
  this year against a full 12 months last year.
- EBIT actual (YTD) is compared against the FULL fiscal year's budget,
  not a prorated slice of it — EBIT has a large fixed-cost component that
  doesn't scale down in slow months the way revenue does, so prorating it
  overstates how far "behind" or "ahead" the business actually is.
"""

import altair as alt
import pandas as pd
import streamlit as st

from styling import PRODUCT_COLORS, NAVY, AMBER, STATUS_GOOD, STATUS_CRITICAL, TEXT_SECONDARY


def render(sales_df, finance_df, as_of):
    year = as_of.year
    finance_df = finance_df.copy()
    finance_df["year"] = finance_df.month.str[:4].astype(int)

    # finance_df carries rows for the WHOLE fiscal year (including months
    # that haven't happened yet), so actuals ("revenue", "cogs", "opex",
    # "ebit", "cash_balance") are NaN there — pandas .sum() skips NaN by
    # default, so filtering to "this year" and summing still correctly
    # gives only the real, happened-so-far total. budget_revenue/
    # budget_ebit, by contrast, ARE populated for the full year — that's
    # what lets "YTD actual vs. full-year budget" be read straight off
    # this one table.
    current = finance_df[finance_df.year == year]
    current_ytd = current[current.revenue.notna()]  # only months that have happened
    prior_cutoff_month = f"{year - 1}-{as_of.month:02d}"
    prior = finance_df[(finance_df.year == year - 1) & (finance_df.month <= prior_cutoff_month)]

    cur_rev = current_ytd.revenue.sum()
    pri_rev = prior.revenue.sum()
    growth = (cur_rev - pri_rev) / pri_rev if pri_rev else 0

    st.subheader("Revenue & Profitability")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Revenue (YTD)", f"${cur_rev:,.0f}", f"{growth:+.1%} vs. same period last year")

    for i, sub in enumerate(sorted(current_ytd.subsidiary.unique())):
        sub_rev = current_ytd[current_ytd.subsidiary == sub].revenue.sum()
        [col2, col3][i].metric(f"Revenue — {sub.replace('Lumin Light ', '')}", f"${sub_rev:,.0f}")

    cur_ebit = current_ytd.ebit.sum()
    full_year_ebit_budget = current.budget_ebit.sum()  # current includes the full 12 months of budget rows
    col4.metric("EBIT (YTD)", f"${cur_ebit:,.0f}",
                f"{cur_ebit/full_year_ebit_budget:.0%} of full-year budget" if full_year_ebit_budget else None)

    st.divider()

    left, right = st.columns([3, 2])

    with left:
        st.markdown("**Revenue: Actual vs. Budget, by Month**")
        # Deliberately uses `current` (the full year, budget included through
        # December) rather than `current_ytd` — the Actual line naturally
        # stops at the current month while Budget keeps going, showing the
        # rest of the year's plan alongside what's already happened.
        chart_df = current.melt(
            id_vars=["month"], value_vars=["revenue", "budget_revenue"],
            var_name="series", value_name="value",
            # min_count=1 keeps an all-NaN group as NaN instead of summing
            # to 0 — without it, future months' "Actual" would plot as a
            # crash to zero instead of the line just stopping.
        ).groupby(["month", "series"], as_index=False).value.sum(min_count=1)
        chart_df["series"] = chart_df["series"].map({"revenue": "Actual", "budget_revenue": "Budget"})
        chart = alt.Chart(chart_df).mark_line(point=True, strokeWidth=2.5).encode(
            x=alt.X("month:N", title=None),
            y=alt.Y("value:Q", title="Revenue ($)"),
            color=alt.Color("series:N", title=None, scale=alt.Scale(
                domain=["Actual", "Budget"], range=[NAVY, AMBER])),
            strokeDash=alt.condition(alt.datum.series == "Budget", alt.value([4, 3]), alt.value([0])),
            tooltip=[alt.Tooltip("month:N", title="Month"), alt.Tooltip("series:N", title="Series"),
                     alt.Tooltip("value:Q", title="Amount", format="$,.0f")],
        ).properties(height=280)
        st.altair_chart(chart, use_container_width=True)

    with right:
        st.markdown("**Gross Margin by Product**")
        won = sales_df[sales_df.status == "Won"].copy()
        won["cogs_total"] = won.quantity * won.unit_cost
        by_product = won.groupby("product").agg(revenue=("deal_value", "sum"), cogs=("cogs_total", "sum"))
        by_product["margin"] = (by_product.revenue - by_product.cogs) / by_product.revenue
        by_product = by_product.reindex(list(PRODUCT_COLORS)).reset_index()
        chart = alt.Chart(by_product).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=32).encode(
            x=alt.X("product:N", title=None, sort=list(PRODUCT_COLORS), axis=alt.Axis(labelAngle=0)),
            y=alt.Y("margin:Q", title="Gross Margin", axis=alt.Axis(format="%")),
            color=alt.Color("product:N", scale=alt.Scale(
                domain=list(PRODUCT_COLORS), range=list(PRODUCT_COLORS.values())), legend=None),
            tooltip=[alt.Tooltip("product:N", title="Product"),
                     alt.Tooltip("margin:Q", title="Margin", format=".1%"),
                     alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f")],
        ).properties(height=280)
        st.altair_chart(chart, use_container_width=True)

    st.divider()
    st.subheader("Cash Position")
    col1, col2, col3 = st.columns(3)

    # finance_df spans the full fiscal year including unhappened future
    # months (see the note at the top of this function) — cash_balance is
    # blank there, so restrict to rows that have actually happened before
    # taking "latest" or "trailing 3 months," or these would silently pick
    # up blank future rows instead of real recent ones.
    happened_df = finance_df[finance_df.cash_balance.notna()]

    latest_month = happened_df.month.max()
    latest_cash = happened_df[happened_df.month == latest_month].cash_balance.sum()
    col1.metric("Cash Balance (latest)", f"${latest_cash:,.0f}", f"as of {latest_month}")

    trailing3 = happened_df.sort_values("month").groupby("subsidiary").tail(3)
    avg_monthly_change = trailing3.net_cash_change.sum() / 3
    col2.metric("Avg. Monthly Cash Change (trailing 3mo)", f"${avg_monthly_change:,.0f}",
                "Generating cash" if avg_monthly_change >= 0 else "Burning cash",
                delta_color="normal" if avg_monthly_change >= 0 else "inverse")

    ebit_margin = cur_ebit / cur_rev if cur_rev else 0
    col3.metric("EBIT Margin (YTD)", f"{ebit_margin:.1%}")

    cash_chart_df = happened_df.groupby("month", as_index=False).cash_balance.sum()
    chart = alt.Chart(cash_chart_df).mark_area(
        line={"color": NAVY, "strokeWidth": 2}, color=alt.Gradient(
            gradient="linear",
            stops=[alt.GradientStop(color="#FFFFFF", offset=0), alt.GradientStop(color="#9EC5F4", offset=1)],
            x1=1, x2=1, y1=1, y2=0,
        ),
    ).encode(
        x=alt.X("month:N", title=None),
        y=alt.Y("cash_balance:Q", title="Cash Balance ($)"),
        tooltip=[alt.Tooltip("month:N", title="Month"), alt.Tooltip("cash_balance:Q", title="Cash", format="$,.0f")],
    ).properties(height=220)
    st.altair_chart(chart, use_container_width=True)
