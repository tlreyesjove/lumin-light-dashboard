"""
Sales pillar, split into two sections per Tatiana's request:

- Performance — what's already happened: deals won YTD, win rate, and the
  revenue mix between Institutional and Commercial clients.
- Pipeline — what's still open: weighted pipeline value by stage, and
  what's expected to close this quarter.

"Target" here isn't hardcoded in this file — it's read from the Finance
tab's budget_revenue (annual sum), which itself comes from the financial
model. That keeps the dashboard's only data source the Google Sheet, per
the project's architecture: three source systems feed the Sheet, the
dashboard reads only from the Sheet.

client_type (Institutional vs. Commercial) is a coarser rollup of
buyer_type, generated alongside it in scripts/generate_sales.py — not
computed here, so the Sales tab in the Sheet already carries it as real
data, the same as any other column.
"""

import altair as alt
import pandas as pd
import streamlit as st

from styling import PRODUCT_COLORS, CLIENT_TYPE_COLORS, STAGE_ORDER, NAVY, AMBER, TEXT_SECONDARY


def current_quarter_bounds(as_of):
    q = (as_of.month - 1) // 3
    start_month = q * 3 + 1
    start = pd.Timestamp(year=as_of.year, month=start_month, day=1)
    end = (start + pd.DateOffset(months=3)) - pd.DateOffset(days=1)
    return start, end


def render(sales_df, finance_df, as_of):
    year = as_of.year
    annual_target = finance_df[finance_df.month.str.startswith(str(year))].budget_revenue.sum()

    open_deals = sales_df[sales_df.status == "Open"]
    won_deals = sales_df[sales_df.status == "Won"]
    lost_deals = sales_df[sales_df.status == "Lost"]
    won_ytd = won_deals[won_deals.actual_close_date.dt.year == year]
    closed = pd.concat([won_deals, lost_deals])

    # --- Performance -----------------------------------------------------
    st.subheader("Performance")
    st.caption("Closed deals and win rate — what's already happened.")

    col1, col2 = st.columns(2)
    won_ytd_value = won_ytd.deal_value.sum()
    col1.metric("Deals Won (YTD)", f"${won_ytd_value:,.0f}",
                f"{won_ytd_value/annual_target:.0%} of annual target")

    win_rate = len(won_deals) / len(closed) if len(closed) else 0
    col2.metric("Win Rate (all-time)", f"{win_rate:.0%}", f"{len(won_deals)} won / {len(closed)} closed")

    st.markdown("**Revenue by Client Type (YTD, Won)**")
    by_client_type = won_ytd.groupby("client_type").deal_value.sum().reindex(list(CLIENT_TYPE_COLORS)).reset_index()
    by_client_type.columns = ["client_type", "revenue"]
    chart = alt.Chart(by_client_type).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=40).encode(
        y=alt.Y("client_type:N", title=None),
        x=alt.X("revenue:Q", title="Revenue ($)"),
        color=alt.Color("client_type:N", scale=alt.Scale(
            domain=list(CLIENT_TYPE_COLORS), range=list(CLIENT_TYPE_COLORS.values())), legend=None),
        tooltip=[alt.Tooltip("client_type:N", title="Client Type"),
                 alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f")],
    ).properties(height=140)
    st.altair_chart(chart, use_container_width=True)
    st.caption("Institutional = Government, NGO, Multilateral. Commercial = Distributor (resellers).")

    st.divider()

    # --- Pipeline ----------------------------------------------------------
    st.subheader("Pipeline")
    st.caption("Open deals — what's still ahead.")

    col1, col2 = st.columns(2)
    weighted_pipeline = open_deals.weighted_value.sum()
    col1.metric("Weighted Pipeline", f"${weighted_pipeline:,.0f}",
                f"{weighted_pipeline/annual_target:.0%} of annual target")

    q_start, q_end = current_quarter_bounds(as_of)
    closing_this_q = open_deals[
        (open_deals.expected_close_date >= q_start) & (open_deals.expected_close_date <= q_end)
    ]
    col2.metric(f"Closing This Quarter (Q{(as_of.month-1)//3+1})", f"{len(closing_this_q)} deals",
                f"${closing_this_q.deal_value.sum():,.0f} value")

    st.markdown("**Weighted Pipeline Value by Stage**")
    by_stage = open_deals.groupby("stage").weighted_value.sum().reindex(STAGE_ORDER).reset_index()
    by_stage.columns = ["stage", "weighted_value"]
    chart = alt.Chart(by_stage).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=48).encode(
        x=alt.X("stage:N", sort=STAGE_ORDER, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("weighted_value:Q", title="Weighted Value ($)"),
        color=alt.value(NAVY),
        tooltip=[alt.Tooltip("stage:N", title="Stage"),
                 alt.Tooltip("weighted_value:Q", title="Weighted Value", format="$,.0f")],
    ).properties(height=280)
    st.altair_chart(chart, use_container_width=True)

    st.divider()
    st.markdown("**Open Pipeline — Detail**")
    display_cols = ["deal_id", "subsidiary", "buyer_type", "client_type", "buyer_name", "product",
                     "deal_value", "stage", "probability", "weighted_value", "expected_close_date"]
    st.dataframe(
        open_deals[display_cols].sort_values("expected_close_date"),
        use_container_width=True, hide_index=True,
        column_config={
            "deal_value": st.column_config.NumberColumn("Deal Value", format="$%,.0f"),
            "probability": st.column_config.NumberColumn("Probability", format="%.0%%"),
            "weighted_value": st.column_config.NumberColumn("Weighted Value", format="$%,.0f"),
            "expected_close_date": st.column_config.DateColumn("Expected Close"),
        },
    )
