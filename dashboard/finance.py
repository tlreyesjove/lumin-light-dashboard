"""
Finance pillar, rebuilt into three sections — same three-part shape as the
Sales tab (Sales Performance / Pipeline / Open Pipeline Detail):

- Financial Performance — a 2x2 chart grid, same style as Sales
  Performance: Recognized Revenue YTD (bullet chart vs. budget), Gross
  Margin by Product Tier (bar chart, Sol 1-5), Recognized Revenue vs.
  Budget by Quarter (bullet chart), and Cash Balance Trend (line, last
  12 happened months).
- Cash & Risk — 8 KPI tiles in two rows, same style as Sales' Pipeline
  scorecards: Cash Balance, Runway, DSO, AR Overdue on top; Gross
  Margin %, Customer Concentration, Opex vs. Budget, EBITDA underneath.
- AR Aging Detail — a table, same style as Sales' Open Pipeline Detail,
  listing every currently-outstanding (non-Paid) invoice.

bullet_chart, money_label, MONEY_AXIS_EXPR, and quarter_bounds are
imported from sales.py rather than duplicated — they're non-trivial,
already-tuned (see sales.py's own history of label-positioning fixes),
and "same style as the Sales tab" is the explicit point of reusing them
rather than rebuilding a second, subtly-different copy.

RECOGNIZED REVENUE vs. BOOKED REVENUE — the one genuinely new concept
this file introduces. "Booked YTD" on the Sales tab is deal_value summed
by actual_close_date — when a deal was WON. Everything on this tab that
says "Revenue" instead sums invoice amount (from the AR tab) by
issue_date — when the deal was actually INVOICED, which happens some
days after it closes (see config.py's AR section). That's what makes
Recognized Revenue a real, separate, slightly LOWER number than Booked
YTD: the tail end of this month's bookings hasn't been invoiced yet, so
it hasn't been recognized yet either. Both numbers describe the exact
same underlying deals — they just answer different questions ("what did
Sales close?" vs. "what can Finance put on the books?").

Everything else on this tab (Gross Margin, Opex, EBIT/EBITDA, Cash) is
still keyed to the existing Finance tab's booking-based revenue/cogs —
introducing a recognition lag into the whole P&L wasn't asked for and
would be a much bigger, more invasive change than two new charts and a
few KPI tiles.
"""

import altair as alt
import pandas as pd
import streamlit as st

from styling import PRODUCT_COLORS, NAVY, AMBER, TEXT_SECONDARY
from sales import bullet_chart, money_label, MONEY_AXIS_EXPR, quarter_bounds


def render(sales_df, finance_df, ar_df, as_of):
    year = as_of.year
    finance_df = finance_df.copy()
    finance_df["year"] = finance_df.month.str[:4].astype(int)
    current = finance_df[finance_df.year == year]
    # Only months that have actually happened — see the note in the old
    # version of this file (and Learning Doc 2.4) on why NaN, not 0, is
    # what an un-happened month's actuals should be.
    current_ytd = current[current.revenue.notna()]
    happened_df = finance_df[finance_df.cash_balance.notna()]

    won = sales_df[sales_df.status == "Won"].copy()
    won["cogs_total"] = won.quantity * won.unit_cost
    won_ytd = won[pd.to_datetime(won.actual_close_date).dt.year == year]

    # ar_df is invoice-level (one row per Closed Won deal). Recognized
    # Revenue is scoped to the SAME cohort as Booked YTD — deals whose
    # actual_close_date falls in `year` — and then only counts the
    # amount actually invoiced by `as_of` (issue_date <= as_of). That
    # "already invoiced" filter is what makes Recognized Revenue a real,
    # always-lower-or-equal subset of Booked: every dollar counted here
    # is also counted in Booked YTD, but not every Booked dollar has
    # cleared its invoicing lag yet. Scoping by the invoice's OWN issue
    # date instead (a first version of this did) pulls in invoices for
    # deals that closed in the PRIOR year — enough of a boundary effect,
    # given how Nov/Dec-heavy this business's seasonality is, to flip
    # Recognized Revenue ABOVE Booked instead of below it.
    ar_df = ar_df.copy()
    ar_ytd = ar_df[(ar_df.actual_close_date.dt.year == year) & (ar_df.issue_date <= as_of)]

    # --- Financial Performance ----------------------------------------------
    st.subheader("Financial Performance")

    row1_left, row1_right = st.columns(2)

    with row1_left:
        st.markdown("**Recognized Revenue YTD**")
        annual_goal = finance_df[finance_df.month.str.startswith(str(year))].budget_revenue.sum()
        recognized_ytd = ar_ytd.amount.sum()
        rev_df = pd.DataFrame([{
            "period": str(year), "goal": annual_goal, "actual": recognized_ytd,
            "pct_of_goal": (recognized_ytd / annual_goal) if annual_goal else 0,
        }])
        st.altair_chart(bullet_chart(rev_df, "period", None, NAVY, 260, y_max=annual_goal + 5_000_000,
                                      y_title="Revenue ($)"),
                         use_container_width=True)

    with row1_right:
        st.markdown("**Gross Margin by Product Tier**")
        by_product = won_ytd.groupby("product").agg(revenue=("deal_value", "sum"), cogs=("cogs_total", "sum"))
        by_product["margin"] = (by_product.revenue - by_product.cogs) / by_product.revenue
        by_product = by_product.reindex(list(PRODUCT_COLORS)).reset_index()
        by_product["margin"] = by_product["margin"].fillna(0)
        by_product["label"] = by_product["margin"].apply(lambda v: f"{v:.0%}")
        margin_tooltip = [alt.Tooltip("product:N", title="Product"),
                           alt.Tooltip("margin:Q", title="Margin", format=".1%"),
                           alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f")]
        margin_base = alt.Chart(by_product)
        margin_bars = margin_base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=32).encode(
            x=alt.X("product:N", title=None, sort=list(PRODUCT_COLORS), axis=alt.Axis(labelAngle=0)),
            y=alt.Y("margin:Q", title="Gross Margin", axis=alt.Axis(format="%")),
            color=alt.Color("product:N", scale=alt.Scale(
                domain=list(PRODUCT_COLORS), range=list(PRODUCT_COLORS.values())), legend=None),
            tooltip=margin_tooltip,
        )
        # Same "label above the bar" treatment used throughout the Sales
        # tab (dy=-10, fontSize=11, TEXT_SECONDARY, shared tooltip).
        margin_labels = margin_base.mark_text(dy=-10, fontWeight="bold", fontSize=11, color=TEXT_SECONDARY).encode(
            x=alt.X("product:N", sort=list(PRODUCT_COLORS)), y=alt.Y("margin:Q"), text=alt.Text("label:N"),
            tooltip=margin_tooltip,
        )
        st.altair_chart((margin_bars + margin_labels).properties(height=260), use_container_width=True)

    row2_left, row2_right = st.columns(2)

    with row2_left:
        st.markdown("**Recognized Revenue vs. Budget, by Quarter**")
        q_rows = []
        for q in range(1, 5):
            q_start, q_end = quarter_bounds(year, q)
            q_months = [f"{year}-{m:02d}" for m in range((q - 1) * 3 + 1, q * 3 + 1)]
            q_goal = finance_df[finance_df.month.isin(q_months)].budget_revenue.sum()
            # Same cohort-plus-already-invoiced logic as Recognized Revenue
            # YTD above: which quarter the deal CLOSED in, filtered down to
            # the portion already invoiced by as_of.
            q_actual = ar_df[(ar_df.actual_close_date >= q_start) & (ar_df.actual_close_date <= q_end)
                              & (ar_df.issue_date <= as_of)].amount.sum()
            q_rows.append({"quarter": f"Q{q} {year}", "goal": q_goal, "actual": q_actual,
                            "pct_of_goal": (q_actual / q_goal) if q_goal else 0})
        q_df = pd.DataFrame(q_rows)
        st.altair_chart(bullet_chart(q_df, "quarter", None, NAVY, 260, x_sort=q_df.quarter.tolist(),
                                      y_title="Revenue ($)"),
                         use_container_width=True)

    with row2_right:
        st.markdown("**Cash Balance Trend**")
        # The current calendar year only (Jan through whichever month has
        # most recently happened) — not a rolling trailing-12 window,
        # which would cross into the prior fiscal year and mix two years'
        # worth of cash history into one chart.
        year_cash = happened_df[happened_df.year == year]
        monthly_cash = year_cash.groupby("month", as_index=False).cash_balance.sum().sort_values("month")
        monthly_cash["series"] = "Actual"

        # Projected cash for the rest of the year — same 1-month
        # collection-lag model generate_finance.py already uses for
        # actuals (this month's cash IN = last month's revenue; cash OUT
        # = this month's costs), just driven by budget_revenue/
        # budget_opex instead, since actuals don't exist yet for months
        # that haven't happened. budget_cogs isn't its own column, but
        # it's fully recoverable algebraically from budget_ebit =
        # budget_revenue - budget_cogs - budget_opex - da — the same
        # relationship actual EBIT already follows — so this needs no
        # new data, just arithmetic on columns already on this tab.
        # Walked per subsidiary (cash timing is a per-entity thing) then
        # summed back together, same as the actual figures above.
        projected_rows = []
        for sub, group in current.sort_values("month").groupby("subsidiary"):
            actual_g = group[group.cash_balance.notna()]
            if actual_g.empty:
                continue
            running_balance = actual_g.cash_balance.iloc[-1]
            prior_revenue = actual_g.revenue.iloc[-1]
            # The last actual month, repeated as the projection's own
            # starting point — makes the dashed line pick up exactly
            # where the solid line ends, instead of a visual gap.
            projected_rows.append({"month": actual_g.month.iloc[-1], "cash_balance": running_balance})
            future_g = group[group.cash_balance.isna()].sort_values("month")
            for _, row in future_g.iterrows():
                budget_cogs = row.budget_revenue - row.budget_opex - row.da - row.budget_ebit
                running_balance += prior_revenue - (budget_cogs + row.budget_opex)
                projected_rows.append({"month": row.month, "cash_balance": running_balance})
                prior_revenue = row.budget_revenue
        projected_cash = pd.DataFrame(projected_rows).groupby("month", as_index=False).cash_balance.sum()
        projected_cash["series"] = "Projected"

        combined_cash = pd.concat([monthly_cash, projected_cash], ignore_index=True)
        cash_tooltip = [alt.Tooltip("month:N", title="Month"), alt.Tooltip("series:N", title="Series"),
                         alt.Tooltip("cash_balance:Q", title="Cash Balance", format="$,.0f")]
        cash_line = alt.Chart(combined_cash).mark_line(point=True, strokeWidth=2.5).encode(
            x=alt.X("month:N", title=None),
            y=alt.Y("cash_balance:Q", title="Cash Balance ($)", axis=alt.Axis(labelExpr=MONEY_AXIS_EXPR)),
            color=alt.Color("series:N", title=None, scale=alt.Scale(
                domain=["Actual", "Projected"], range=[NAVY, AMBER])),
            strokeDash=alt.condition(alt.datum.series == "Projected", alt.value([4, 3]), alt.value([0])),
            tooltip=cash_tooltip,
        ).properties(height=260)
        st.altair_chart(cash_line, use_container_width=True)

    st.divider()

    # --- Cash & Risk ----------------------------------------------------------
    st.subheader("Cash & Risk")

    latest_month = happened_df.month.max()
    latest_cash = happened_df[happened_df.month == latest_month].cash_balance.sum()

    trailing3 = happened_df.sort_values("month").groupby("subsidiary").tail(3)
    avg_monthly_change = trailing3.net_cash_change.sum() / 3

    # DSO: average days from invoice ISSUE to actual PAYMENT, across every
    # Paid invoice on record (both years) — the trailing-N-month Paid
    # population in a single subsidiary is small enough (this is a ~$23M/
    # year business, not a high-volume one) that an all-time average is
    # the more statistically stable read of "how long we actually take
    # to get paid," not a noisier last-few-months slice.
    paid = ar_df[ar_df.status == "Paid"]
    dso = (paid.paid_date - paid.issue_date).dt.days.mean() if len(paid) else None

    ar_overdue = ar_df[ar_df.status == "Overdue"].amount.sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cash Balance", f"${latest_cash:,.0f}", f"as of {latest_month}")
    if avg_monthly_change < 0:
        runway_months = latest_cash / abs(avg_monthly_change)
        col2.metric("Runway", f"{runway_months:,.1f} months", "at current burn", delta_color="off")
    else:
        col2.metric("Runway", "N/A", "cash flow positive")
    col3.metric("DSO", f"{dso:,.0f} days" if dso is not None else "—")
    col4.metric("AR Overdue", f"${ar_overdue:,.0f}")

    # Gross Margin %: company-wide, YTD, from the same Won-deal figures
    # the Gross Margin by Product Tier chart above already computes per
    # tier — this is just the blended total instead of a per-tier split.
    gm_revenue, gm_cogs = won_ytd.deal_value.sum(), won_ytd.cogs_total.sum()
    gross_margin_pct = (gm_revenue - gm_cogs) / gm_revenue if gm_revenue else 0

    # Customer Concentration: top 5 customers' share of YTD booked
    # revenue — deliberately booked (deal_value), not recognized/invoiced,
    # since "which customers make up our business" is a sales-relationship
    # question, not an accounting-timing one.
    by_customer = won_ytd.groupby("buyer_name").deal_value.sum().sort_values(ascending=False)
    top5_pct = (by_customer.head(5).sum() / by_customer.sum()) if len(by_customer) and by_customer.sum() else 0

    # Opex vs. Budget: actual opex for the months that have happened
    # against budget_opex for those SAME months (not the full year) — a
    # direct like-for-like comparison, the same way the Revenue
    # Actual-vs-Budget chart already compares matching months rather
    # than prorating a single annual total.
    actual_opex_ytd = current_ytd.opex.sum()
    budget_opex_ytd = current_ytd.budget_opex.sum()  # current_ytd already scoped to happened months
    opex_variance = (actual_opex_ytd - budget_opex_ytd) / budget_opex_ytd if budget_opex_ytd else 0

    # EBITDA: EBIT + D&A, both already computed upstream — da is exposed
    # as its own column in generate_finance.py specifically so this
    # doesn't need to re-derive the underlying assumption here.
    ebitda_ytd = current_ytd.ebit.sum() + current_ytd.da.sum()

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Gross Margin %", f"{gross_margin_pct:.1%}")
    col6.metric("Customer Concentration", f"{top5_pct:.0%}", "top 5 customers")
    col7.metric("Opex vs. Budget", f"{opex_variance:+.1%}",
                "over budget" if opex_variance > 0 else "under budget",
                delta_color="inverse")
    col8.metric("EBITDA", f"${ebitda_ytd:,.0f}")

    st.divider()

    # --- AR Aging Detail --------------------------------------------------
    st.markdown("**AR Aging Detail**")
    outstanding = ar_df[ar_df.status != "Paid"].sort_values("days_overdue", ascending=False)
    display_cols = ["invoice_id", "subsidiary", "buyer_type", "buyer_name", "amount", "days_overdue", "status"]
    st.dataframe(
        outstanding[display_cols],
        use_container_width=True, hide_index=True,
        column_config={
            "invoice_id": st.column_config.TextColumn("Invoice ID"),
            "subsidiary": st.column_config.TextColumn("Entity"),
            "buyer_type": st.column_config.TextColumn("Customer Category"),
            "buyer_name": st.column_config.TextColumn("Customer"),
            "amount": st.column_config.NumberColumn("Amount", format="dollar", step=1),
            "days_overdue": st.column_config.NumberColumn("Days Overdue", format="localized"),
            "status": st.column_config.TextColumn("Status"),
        },
    )
