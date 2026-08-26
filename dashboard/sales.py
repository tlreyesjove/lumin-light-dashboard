"""
Sales pillar, split into two sections per Tatiana's request:

- Sales Performance — what's already happened, as 4 report panels:
  Sales YTD (actual vs. annual goal), Sales by Quarter (actual vs. each
  quarter's goal), Sales by Channel (Institutional vs. Commercial share),
  and Win/Loss Rate (a diverging bar, by deal count: won / (won + lost)).
- Pipeline — what's still open, as 4 scorecards (Weighted Pipeline, Open
  Deals, Avg. Sales Cycle, Avg. Order Value) plus a Revenue Forecast by
  Month chart (Open by expected close date vs. Won by actual close date,
  both weighted, monthly and NOT cumulative, starting this month rather
  than January — modeled on a Pipedrive forecast report Tatiana shared).

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

from styling import PRODUCT_COLORS, CLIENT_TYPE_COLORS, WIN_LOSS_COLORS, NAVY, AMBER, TEXT_SECONDARY, BORDER

GOAL_COLOR = BORDER


def quarter_bounds(year, q):
    start = pd.Timestamp(year=year, month=(q - 1) * 3 + 1, day=1)
    end = (start + pd.DateOffset(months=3)) - pd.DateOffset(days=1)
    return start, end


def money_label(v):
    """"$1.7M" / "$330K" style — used for the on-chart text labels."""
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:,.1f}M"
    return f"${v/1_000:,.0f}K"


# Same "$1.7M" / "$330K" / "$0" style as money_label(), but as a Vega
# expression — for AXIS TICKS, which Vega generates itself from the scale
# (not from a dataframe column money_label() could run over in Python).
# Vega's own "s" format type would give "$950k" (lowercase k for
# thousands, though uppercase M/G/etc. above it) — this forces uppercase
# K to match money_label() exactly, and special-cases 0 to show as plain
# "$0" rather than "$0K".
MONEY_AXIS_EXPR = (
    "datum.value == 0 ? '$0' : "
    "(abs(datum.value) >= 1000000 ? '$' + format(datum.value / 1000000, '.1f') + 'M' : "
    "'$' + format(datum.value / 1000, '.0f') + 'K')"
)


def bullet_chart(df, x_field, x_title, actual_color, height, x_sort=None, y_max=None):
    """Shared "actual vs. goal" bar: a light gray bar sized to the goal,
    with a colored bar for the actual value drawn on top of it — same
    idea as Tatiana's reference screenshots (a target bracket behind a
    solid progress bar). Both layers share one tooltip (Goal, Deals Won,
    Difference, % of Goal) so hovering anywhere on the column — the gray
    goal portion or the colored actual portion — shows the same clean
    card, instead of Altair's default raw-field tooltip on whichever
    layer doesn't have one explicitly set.

    Note: Altair/Vega-Lite tooltips are a plain list of label/value rows
    — no colored text, no rounded badge, no divider line. This matches
    Tatiana's reference CONTENT (title, %, Goal, Deals Won, Difference)
    as closely as a declarative Altair tooltip can; the reference's exact
    visual polish would need a custom Vega tooltip handler, a bigger build.
    """
    df = df.copy()
    df["difference"] = df["actual"] - df["goal"]
    df["difference_label"] = df["difference"].apply(lambda v: f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}")
    df["goal_label"] = df["goal"].apply(lambda v: f"{money_label(v)} \U0001F3AF")  # \U0001F3AF = 🎯
    df["actual_label"] = df["actual"].apply(money_label)
    # Two labels, two clearly separate zones, so they can never collide no
    # matter which value is bigger or how close the two are:
    #   - Goal always sits OUTSIDE any bar — anchored at whichever of
    #     goal/actual is taller, then nudged further up. Earlier this was
    #     anchored at the goal value itself, which put it inside the
    #     actual-color bar whenever actual beat goal (needing a
    #     conditional light/dark color to stay readable) — and a
    #     since-reverted attempt anchored it at a fraction of the SMALLER
    #     value, which fixed close-value collisions but broke the normal
    #     case (goal clearly bigger than actual put the goal's own label
    #     at a height with no relation to the goal value it displays).
    #   - Actual always sits INSIDE its own bar, vertically centered —
    #     freeing up the top entirely for the goal label, so the two
    #     never compete for the same space regardless of the numbers.
    df["goal_label_y"] = df[["goal", "actual"]].max(axis=1)
    df["actual_label_y"] = df["actual"] * 0.5
    # actual_label sits inside its own bar, which needs a light color to
    # read against the dark fill — except when actual is 0 (no bar at
    # all), where that same light label would sit on the page's white
    # background and disappear. Dark text there instead.
    df["actual_label_color"] = df["actual"].apply(lambda v: "#F7F8FA" if v > 0 else TEXT_SECONDARY)

    y_scale = alt.Scale(domain=[0, y_max]) if y_max else alt.Undefined

    tooltip = [
        alt.Tooltip(f"{x_field}:N", title=x_title or " "),
        alt.Tooltip("pct_of_goal:Q", title="% of Goal", format=".0%"),
        alt.Tooltip("goal:Q", title="Goal", format="$,.0f"),
        alt.Tooltip("actual:Q", title="Deals Won", format="$,.0f"),
        alt.Tooltip("difference_label:N", title="Difference"),
    ]

    base = alt.Chart(df)
    goal_bars = base.mark_bar(size=52, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=GOAL_COLOR).encode(
        x=alt.X(f"{x_field}:N", title=x_title, sort=x_sort, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("goal:Q", title="Sales ($)", scale=y_scale, axis=alt.Axis(labelExpr=MONEY_AXIS_EXPR)),
        tooltip=tooltip,
    )
    actual_bars = base.mark_bar(size=52, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=actual_color).encode(
        x=alt.X(f"{x_field}:N", sort=x_sort),
        y=alt.Y("actual:Q", scale=y_scale),
        tooltip=tooltip,
    )
    # Both label marks get the same explicit tooltip as the bars — without
    # it, hovering directly on the label TEXT (a real, if small, hit area)
    # falls back to Altair's default tooltip, dumping every encoded field
    # verbatim — including internal helper columns like goal_label_color,
    # which mean nothing to a viewer.
    goal_labels = base.mark_text(dy=-10, fontWeight="bold", fontSize=11, color=TEXT_SECONDARY).encode(
        x=alt.X(f"{x_field}:N", sort=x_sort), y=alt.Y("goal_label_y:Q", scale=y_scale), text=alt.Text("goal_label:N"),
        tooltip=tooltip,
    )
    actual_labels = base.mark_text(fontWeight="bold", fontSize=11).encode(
        x=alt.X(f"{x_field}:N", sort=x_sort), y=alt.Y("actual_label_y:Q", scale=y_scale), text=alt.Text("actual_label:N"),
        color=alt.Color("actual_label_color:N", scale=None, legend=None),
        tooltip=tooltip,
    )
    return (goal_bars + actual_bars + goal_labels + actual_labels).properties(height=height)


def render(sales_df, finance_df, as_of, entity="Lumin Group Consolidated"):
    year = as_of.year
    entity_label = "Lumin Group" if entity == "Lumin Group Consolidated" else entity.replace("Lumin Light ", "")

    open_deals = sales_df[sales_df.status == "Open"]
    won_deals = sales_df[sales_df.status == "Won"]
    lost_deals = sales_df[sales_df.status == "Lost"]
    won_ytd = won_deals[won_deals.actual_close_date.dt.year == year]
    lost_ytd = lost_deals[lost_deals.actual_close_date.dt.year == year]
    closed = pd.concat([won_deals, lost_deals])
    closed_ytd = pd.concat([won_ytd, lost_ytd])

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
        st.altair_chart(bullet_chart(ytd_df, "period", None, NAVY, 260, y_max=annual_goal + 5_000_000), use_container_width=True)

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
            lambda r: f"{money_label(r.revenue)} ({r.pct:.0%})", axis=1)
        base = alt.Chart(by_client_type).encode(
            theta=alt.Theta("revenue:Q", stack=True),
            color=alt.Color("client_type:N", title=None, scale=alt.Scale(
                domain=list(CLIENT_TYPE_COLORS), range=list(CLIENT_TYPE_COLORS.values())),
                legend=alt.Legend(orient="bottom", symbolType="circle")),
            tooltip=[alt.Tooltip("client_type:N", title="Client Type"),
                     alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                     alt.Tooltip("pct:Q", title="Share", format=".0%")],
        )
        pie = base.mark_arc(outerRadius=65)
        # color=alt.value(...) is required, not the mark-level color=
        # property — pie_labels shares `base`'s color-by-client_type
        # ENCODING, which otherwise overrides any mark property and makes
        # each label render in its own slice's color (amber text on an
        # amber slice is nearly invisible — exactly the "hidden behind
        # the chart" look Tatiana flagged).
        pie_tooltip = [alt.Tooltip("client_type:N", title="Client Type"),
                       alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                       alt.Tooltip("pct:Q", title="Share", format=".0%")]
        pie_labels = base.mark_text(radius=100, fontWeight="bold", fontSize=11).encode(
            text="label:N", color=alt.value(TEXT_SECONDARY), tooltip=pie_tooltip,
        )
        st.altair_chart(
            (pie + pie_labels).properties(height=260, padding={"left": 55, "right": 55, "top": 10, "bottom": 10}),
            use_container_width=True,
        )
        st.caption("Institutional: government, NGO, multilateral")
        st.caption("Commercial: distributors, resellers")

    with row2_right:
        st.markdown("**Win/Loss Rate (YTD)**")
        # Scoped to the current year — won_deals/lost_deals on their own
        # are all-time (2025 + 2026 combined), which is why an earlier
        # version of this showed a much bigger dollar figure than expected
        # on hover. won_ytd/lost_ytd are computed once, near the top.
        # Win rate = won deals / (won + lost) deals — a count, not a dollar
        # weighting. Loss rate is the same denominator with lost as the
        # numerator, so the two always add to exactly 100%.
        n_won, n_lost = len(won_ytd), len(lost_ytd)
        n_closed = n_won + n_lost
        win_amt, loss_amt = won_ytd.deal_value.sum(), lost_ytd.deal_value.sum()
        wl_df = pd.DataFrame([
            {"label": entity_label, "outcome": "Win", "pct": (n_won / n_closed) if n_closed else 0,
             "count": n_won, "amount": win_amt},
            {"label": entity_label, "outcome": "Loss", "pct": -(n_lost / n_closed) if n_closed else 0,
             "count": n_lost, "amount": loss_amt},
        ])
        wl_chart = alt.Chart(wl_df).mark_bar(size=80, cornerRadius=4).encode(
            x=alt.X("label:N", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("pct:Q", title=None, axis=alt.Axis(format="%")),
            color=alt.Color("outcome:N", title=None, scale=alt.Scale(
                domain=list(WIN_LOSS_COLORS), range=list(WIN_LOSS_COLORS.values())),
                legend=alt.Legend(orient="bottom", symbolType="circle")),
            tooltip=[alt.Tooltip("outcome:N", title="Outcome"),
                     alt.Tooltip("pct:Q", title="Rate", format=".1%"),
                     alt.Tooltip("count:Q", title="Deals", format=",.0f"),
                     alt.Tooltip("amount:Q", title="Value", format="$,.0f")],
        )
        wl_tooltip = [alt.Tooltip("outcome:N", title="Outcome"),
                      alt.Tooltip("pct:Q", title="Rate", format=".1%"),
                      alt.Tooltip("count:Q", title="Deals", format=",.0f"),
                      alt.Tooltip("amount:Q", title="Value", format="$,.0f")]
        wl_labels = alt.Chart(wl_df).mark_text(fontWeight="bold", fontSize=12, dy=alt.expr("datum.pct > 0 ? -8 : 14")).encode(
            x=alt.X("label:N"), y=alt.Y("pct:Q"), text=alt.Text("pct:Q", format=".0%"), tooltip=wl_tooltip,
        )
        st.altair_chart((wl_chart + wl_labels).properties(height=260), use_container_width=True)

    st.divider()

    # --- Pipeline -----------------------------------------------------------
    st.subheader("Pipeline")

    col1, col2, col3, col4 = st.columns(4)
    annual_target = finance_df[finance_df.month.str.startswith(str(year))].budget_revenue.sum()
    weighted_pipeline = open_deals.weighted_value.sum()
    col1.metric("Weighted Pipeline", f"${weighted_pipeline:,.0f}")
    # st.metric's delta_color="off" only removes the color, not the arrow
    # glyph itself — there's no built-in way to show delta text with no
    # arrow at all, so this is a plain caption underneath instead of the
    # metric's own delta.
    if annual_target:
        col1.caption(f"{weighted_pipeline/annual_target:.0%} of annual target")

    col2.metric("Open Deals", f"{len(open_deals):,}")

    # Average Sales Cycle: days from created to actual close, for deals
    # that have actually closed (won OR lost) — scoped to this year (YTD),
    # same reasoning as Win/Loss Rate: won_deals/lost_deals alone are
    # all-time (2025+2026), which would silently mix in a different year.
    if len(closed_ytd):
        avg_cycle_days = (closed_ytd.actual_close_date - closed_ytd.created_date).dt.days.mean()
        col3.metric("Avg. Sales Cycle (YTD)", f"{avg_cycle_days:,.0f} days")
    else:
        col3.metric("Avg. Sales Cycle (YTD)", "—")

    # Average Order Value: average size of actual booked business (Won),
    # not open or lost deals — also YTD, for the same reason.
    if len(won_ytd):
        col4.metric("Avg. Order Value (YTD)", f"${won_ytd.deal_value.mean():,.0f}")
    else:
        col4.metric("Avg. Order Value (YTD)", "—")

    st.markdown("**Revenue Forecast by Month**")
    st.caption("Monthly, not cumulative — Open (by expected close date) vs. Won (by actual close date), both weighted. "
               "Forward-looking: starts this month, not January.")
    # Starts at the CURRENT month, not Jan 1 — a forecast should look
    # ahead, not dwell on months that have already happened. This means
    # the window naturally shrinks as the year goes on (5 months left in
    # August, 1 month left in December) rather than always showing 12.
    forecast_months = pd.date_range(f"{year}-{as_of.month:02d}-01", f"{year}-12-01", freq="MS")

    open_by_month = open_deals.copy()
    open_by_month["month"] = open_by_month.expected_close_date.dt.to_period("M").dt.to_timestamp()
    open_grouped = open_by_month[open_by_month.month.dt.year == year].groupby("month").weighted_value.sum()

    won_by_month = won_deals.copy()
    won_by_month["month"] = won_by_month.actual_close_date.dt.to_period("M").dt.to_timestamp()
    won_grouped = won_by_month[won_by_month.month.dt.year == year].groupby("month").weighted_value.sum()

    forecast_rows = []
    for m in forecast_months:
        label = m.strftime("%b %Y")
        forecast_rows.append({"month": label, "month_sort": m, "series": "Open", "value": open_grouped.get(m, 0.0)})
        forecast_rows.append({"month": label, "month_sort": m, "series": "Won", "value": won_grouped.get(m, 0.0)})
    forecast_df = pd.DataFrame(forecast_rows)
    month_order = [m.strftime("%b %Y") for m in forecast_months]
    forecast_colors = {"Open": PRODUCT_COLORS["Sol 1"], "Won": NAVY}

    # No xOffset here — with only one of the two series usually non-zero
    # in a given month (Won for months already closed, Open for months
    # still ahead), an xOffset grouped-bar layout put the one visible bar
    # at the 1/4 or 3/4 mark of its month's slot instead of centered under
    # the tick label, which is what looked "off-centered." Both series
    # share the same x position instead; since they're rarely both
    # meaningfully non-zero in the same month, they don't actually
    # obscure each other in practice.
    forecast_chart = alt.Chart(forecast_df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=36).encode(
        x=alt.X("month:N", title=None, sort=month_order, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("value:Q", title="Weighted Value ($)", axis=alt.Axis(labelExpr=MONEY_AXIS_EXPR)),
        color=alt.Color("series:N", title=None, scale=alt.Scale(
            domain=["Open", "Won"], range=[forecast_colors["Open"], forecast_colors["Won"]]),
            legend=alt.Legend(orient="bottom", symbolType="circle")),
        tooltip=[alt.Tooltip("month:N", title="Month"), alt.Tooltip("series:N", title="Status"),
                 alt.Tooltip("value:Q", title="Weighted Value", format="$,.0f")],
    ).properties(height=280)
    st.altair_chart(forecast_chart, use_container_width=True)

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
