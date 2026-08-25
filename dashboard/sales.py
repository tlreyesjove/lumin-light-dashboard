"""
Sales pillar, split into two sections per Tatiana's request:

- Sales Performance — what's already happened, as 4 report panels:
  Sales YTD (actual vs. annual goal), Sales by Quarter (actual vs. each
  quarter's goal), Sales by Channel (Institutional vs. Commercial share),
  and Win/Loss Rate (a diverging bar, revenue-weighted).
- Pipeline — what's still open: weighted pipeline value by stage, and
  what's expected to close this quarter.

Goals (in the bullet-style charts) come from the Finance tab's
budget_revenue — annual and quarterly totals are both just sums of that
same column, not a separate number. Quarterly goals in particular now
reflect the explicit 2026 quarterly target split (10/20/30/40) set in the
financial model, not the old flat monthly seasonality curve — see
Learning Doc 2.5.

client_type (Institutional vs. Commercial) is a coarser rollup of
buyer_type, generated alongside it in scripts/generate_sales.py — not
computed here, so the Sales tab in the Sheet already carries it as real
data, the same as any other column.

The whole tab (like Finance and Inventory) is filtered upstream in
app.py by the Consolidated/USA/Nigeria entity selector — this file has
no awareness of that filter beyond already receiving a pre-filtered
sales_df/finance_df; `entity` is passed through only for chart labeling.
"""

import altair as alt
import pandas as pd
import streamlit as st

from styling import PRODUCT_COLORS, CLIENT_TYPE_COLORS, STAGE_ORDER, STATUS_GOOD, STATUS_CRITICAL, NAVY, AMBER, TEXT_SECONDARY, BORDER

GOAL_COLOR = BORDER


def current_quarter_bounds(as_of):
    q = (as_of.month - 1) // 3
    start_month = q * 3 + 1
    start = pd.Timestamp(year=as_of.year, month=start_month, day=1)
    end = (start + pd.DateOffset(months=3)) - pd.DateOffset(days=1)
    return start, end


def quarter_bounds(year, q):
    start = pd.Timestamp(year=year, month=(q - 1) * 3 + 1, day=1)
    end = (start + pd.DateOffset(months=3)) - pd.DateOffset(days=1)
    return start, end


def bullet_chart(df, x_field, x_title, actual_color, height, x_sort=None):
    """Shared "actual vs. goal" bar: a light gray bar sized to the goal,
    with a colored bar for the actual value drawn on top of it — same
    idea as Tatiana's reference screenshots (a target bracket behind a
    solid progress bar)."""
    base = alt.Chart(df)
    goal_bars = base.mark_bar(size=52, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=GOAL_COLOR).encode(
        x=alt.X(f"{x_field}:N", title=x_title, sort=x_sort, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("goal:Q", title="Deal Value ($)"),
    )
    actual_bars = base.mark_bar(size=52, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=actual_color).encode(
        x=alt.X(f"{x_field}:N", sort=x_sort),
        y=alt.Y("actual:Q"),
        tooltip=[
            alt.Tooltip(f"{x_field}:N", title=x_title),
            alt.Tooltip("goal:Q", title="Goal", format="$,.0f"),
            alt.Tooltip("actual:Q", title="Deals Won", format="$,.0f"),
            alt.Tooltip("pct_of_goal:Q", title="% of Goal", format=".0%"),
        ],
    )
    goal_labels = base.mark_text(dy=-10, fontWeight="bold", color=TEXT_SECONDARY, fontSize=11).encode(
        x=alt.X(f"{x_field}:N", sort=x_sort), y=alt.Y("goal:Q"), text=alt.Text("goal:Q", format="$.2s"),
    )
    actual_labels = base.mark_text(dy=-8, fontWeight="bold", color=actual_color, fontSize=11).encode(
        x=alt.X(f"{x_field}:N", sort=x_sort), y=alt.Y("actual:Q"), text=alt.Text("actual:Q", format="$.2s"),
    )
    return (goal_bars + actual_bars + goal_labels + actual_labels).properties(height=height)


def render(sales_df, finance_df, as_of, entity="Lumin Group Consolidated"):
    year = as_of.year
    entity_label = "Lumin Group" if entity == "Lumin Group Consolidated" else entity.replace("Lumin Light ", "")

    open_deals = sales_df[sales_df.status == "Open"]
    won_deals = sales_df[sales_df.status == "Won"]
    lost_deals = sales_df[sales_df.status == "Lost"]
    won_ytd = won_deals[won_deals.actual_close_date.dt.year == year]
    closed = pd.concat([won_deals, lost_deals])

    # --- Sales Performance ------------------------------------------------
    st.subheader("Sales Performance")

    row1_left, row1_right = st.columns(2)

    with row1_left:
        st.markdown("**Sales YTD**")
        annual_goal = finance_df[finance_df.month.str.startswith(str(year))].budget_revenue.sum()
        ytd_df = pd.DataFrame([{
            "period": str(year), "goal": annual_goal, "actual": won_ytd.deal_value.sum(),
            "pct_of_goal": (won_ytd.deal_value.sum() / annual_goal) if annual_goal else 0,
        }])
        st.altair_chart(bullet_chart(ytd_df, "period", None, NAVY, 260), use_container_width=True)

    with row1_right:
        st.markdown("**Sales by Quarter**")
        q_rows = []
        for q in range(1, 5):
            q_start, q_end = quarter_bounds(year, q)
            q_months = [f"{year}-{m:02d}" for m in range((q - 1) * 3 + 1, q * 3 + 1)]
            q_goal = finance_df[finance_df.month.isin(q_months)].budget_revenue.sum()
            q_actual = won_deals[(won_deals.actual_close_date >= q_start) & (won_deals.actual_close_date <= q_end)].deal_value.sum()
            q_rows.append({"quarter": f"Q{q} {year}", "goal": q_goal, "actual": q_actual,
                            "pct_of_goal": (q_actual / q_goal) if q_goal else 0})
        q_df = pd.DataFrame(q_rows)
        st.altair_chart(bullet_chart(q_df, "quarter", None, NAVY, 260, x_sort=q_df.quarter.tolist()), use_container_width=True)

    row2_left, row2_right = st.columns(2)

    with row2_left:
        st.markdown("**Sales by Channel**")
        by_client_type = won_ytd.groupby("client_type").deal_value.sum().reindex(list(CLIENT_TYPE_COLORS)).reset_index()
        by_client_type.columns = ["client_type", "revenue"]
        total_rev = by_client_type.revenue.sum()
        by_client_type["pct"] = by_client_type.revenue / total_rev if total_rev else 0
        by_client_type["label"] = by_client_type.apply(
            lambda r: f"${r.revenue/1000:,.0f}K ({r.pct:.0%})", axis=1)
        base = alt.Chart(by_client_type).encode(
            theta=alt.Theta("revenue:Q", stack=True),
            color=alt.Color("client_type:N", title=None, scale=alt.Scale(
                domain=list(CLIENT_TYPE_COLORS), range=list(CLIENT_TYPE_COLORS.values())),
                legend=alt.Legend(orient="bottom")),
            tooltip=[alt.Tooltip("client_type:N", title="Client Type"),
                     alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                     alt.Tooltip("pct:Q", title="Share", format=".0%")],
        )
        donut = base.mark_arc(innerRadius=60, cornerRadius=3)
        donut_labels = base.mark_text(radius=100, fontWeight="bold", fontSize=11, color=TEXT_SECONDARY).encode(text="label:N")
        st.altair_chart((donut + donut_labels).properties(height=260), use_container_width=True)
        st.caption("Institutional = Government, NGO, Multilateral. Commercial = Distributor (resellers).")

    with row2_right:
        st.markdown("**Win/Loss Rate**")
        win_amt = won_deals.deal_value.sum()
        loss_amt = lost_deals.deal_value.sum()
        total_amt = win_amt + loss_amt
        wl_df = pd.DataFrame([
            {"label": entity_label, "outcome": "Win", "pct": (win_amt / total_amt) if total_amt else 0, "amount": win_amt},
            {"label": entity_label, "outcome": "Loss", "pct": -(loss_amt / total_amt) if total_amt else 0, "amount": loss_amt},
        ])
        wl_chart = alt.Chart(wl_df).mark_bar(size=80, cornerRadius=4).encode(
            x=alt.X("label:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("pct:Q", title=None, axis=alt.Axis(format="%")),
            color=alt.Color("outcome:N", title=None, scale=alt.Scale(
                domain=["Win", "Loss"], range=[STATUS_GOOD, STATUS_CRITICAL]), legend=alt.Legend(orient="bottom")),
            tooltip=[alt.Tooltip("outcome:N", title="Outcome"),
                     alt.Tooltip("pct:Q", title="Rate", format=".1%"),
                     alt.Tooltip("amount:Q", title="Value", format="$,.0f")],
        )
        wl_labels = alt.Chart(wl_df).mark_text(fontWeight="bold", fontSize=12, dy=alt.expr("datum.pct > 0 ? -8 : 14")).encode(
            x=alt.X("label:N"), y=alt.Y("pct:Q"), text=alt.Text("pct:Q", format=".0%"),
        )
        st.altair_chart((wl_chart + wl_labels).properties(height=260), use_container_width=True)
        st.caption(f"All-time, revenue-weighted — {len(won_deals)} won / {len(lost_deals)} lost, total ${total_amt:,.0f} closed.")

    st.divider()

    # --- Pipeline -----------------------------------------------------------
    st.subheader("Pipeline")
    st.caption("Open deals — what's still ahead.")

    col1, col2 = st.columns(2)
    annual_target = finance_df[finance_df.month.str.startswith(str(year))].budget_revenue.sum()
    weighted_pipeline = open_deals.weighted_value.sum()
    col1.metric("Weighted Pipeline", f"${weighted_pipeline:,.0f}",
                f"{weighted_pipeline/annual_target:.0%} of annual target" if annual_target else None)

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
