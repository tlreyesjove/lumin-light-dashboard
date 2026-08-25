"""
Sales pillar: pipeline weighted value by stage, deals won YTD, deals closing
this quarter, win rate overall and by buyer type.

"Target" here isn't hardcoded in this file — it's read from the Finance
tab's budget_revenue (annual sum), which itself comes from the financial
model. That keeps the dashboard's only data source the Google Sheet, per
the project's architecture: three source systems feed the Sheet, the
dashboard reads only from the Sheet.
"""

import altair as alt
import pandas as pd
import streamlit as st

from styling import PRODUCT_COLORS, BUYER_TYPE_COLORS, STAGE_ORDER, NAVY, AMBER, TEXT_SECONDARY


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

    st.subheader("Pipeline & Bookings")
    col1, col2, col3, col4 = st.columns(4)

    weighted_pipeline = open_deals.weighted_value.sum()
    col1.metric("Weighted Pipeline", f"${weighted_pipeline:,.0f}",
                f"{weighted_pipeline/annual_target:.0%} of annual target")

    won_ytd_value = won_ytd.deal_value.sum()
    col2.metric("Deals Won (YTD)", f"${won_ytd_value:,.0f}",
                f"{won_ytd_value/annual_target:.0%} of annual target")

    q_start, q_end = current_quarter_bounds(as_of)
    closing_this_q = open_deals[
        (open_deals.expected_close_date >= q_start) & (open_deals.expected_close_date <= q_end)
    ]
    col3.metric(f"Closing This Quarter (Q{(as_of.month-1)//3+1})", f"{len(closing_this_q)} deals",
                f"${closing_this_q.deal_value.sum():,.0f} value")

    closed = pd.concat([won_deals, lost_deals])
    win_rate = len(won_deals) / len(closed) if len(closed) else 0
    col4.metric("Win Rate (all-time)", f"{win_rate:.0%}", f"{len(won_deals)} won / {len(closed)} closed")

    st.divider()

    left, right = st.columns([3, 2])

    with left:
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

    with right:
        st.markdown("**Win Rate by Buyer Type**")
        rows = []
        for bt in BUYER_TYPE_COLORS:
            bt_won = won_deals[won_deals.buyer_type == bt]
            bt_closed = closed[closed.buyer_type == bt]
            rate = len(bt_won) / len(bt_closed) if len(bt_closed) else 0
            rows.append({"buyer_type": bt, "win_rate": rate, "closed": len(bt_closed)})
        wr_df = pd.DataFrame(rows)
        chart = alt.Chart(wr_df).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=28).encode(
            y=alt.Y("buyer_type:N", title=None, sort="-x"),
            x=alt.X("win_rate:Q", title="Win Rate", axis=alt.Axis(format="%")),
            color=alt.Color("buyer_type:N", scale=alt.Scale(
                domain=list(BUYER_TYPE_COLORS.keys()), range=list(BUYER_TYPE_COLORS.values())), legend=None),
            tooltip=[alt.Tooltip("buyer_type:N", title="Buyer Type"),
                     alt.Tooltip("win_rate:Q", title="Win Rate", format=".0%"),
                     alt.Tooltip("closed:Q", title="Deals Closed")],
        ).properties(height=280)
        st.altair_chart(chart, use_container_width=True)

    st.divider()
    st.markdown("**Open Pipeline — Detail**")
    display_cols = ["deal_id", "subsidiary", "buyer_type", "buyer_name", "product",
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
