"""
Sales pillar, split into two sections per Tatiana's request:

- Sales Performance — what's already happened, as 4 report panels:
  Sales YTD (actual vs. annual goal), Sales by Quarter (actual vs. each
  quarter's goal), Sales by Channel (Institutional vs. Commercial share,
  as a pie — plus two semicircular gauges underneath, in the same
  bordered container, showing each channel's YTD revenue against its own
  target), and Win/Loss Rate (a diverging bar, by deal count: won /
  (won + lost)).
- Pipeline — what's still open, as 4 scorecards (Revenue Forecast /
  Weighted Pipeline, Open Deals, Avg. Sales Cycle, Avg. Order Value) plus
  a Revenue Forecast by Month chart (Open by expected close date vs. Won
  by actual close date, both weighted, monthly and NOT cumulative,
  starting this month rather than January — modeled on a Pipedrive
  forecast report Tatiana shared). There's deliberately no separate
  "Revenue Forecast" scorecard distinct from Weighted Pipeline — an
  earlier version had one that quietly folded in this month's already-Won
  revenue, which read as forward-looking while actually mixing in the
  past.

Goals (in the bullet-style charts) come from the Finance tab's
budget_revenue — annual and quarterly totals are both just sums of that
same column, not a separate number. Quarterly goals in particular now
reflect the explicit 2026 quarterly target split (10/20/30/40) set in the
financial model, not the old flat monthly seasonality curve — see
Learning Doc 2.5. Channel targets (the two gauges under Sales by Channel)
work the same way, from budget_institutional_revenue/
budget_commercial_revenue — 2026 only, since there's no channel target
for a year that's already closed out.

client_type (Institutional vs. Commercial) is a coarser rollup of
buyer_type, generated alongside it in scripts/generate_sales.py — not
computed here, so the Sales tab in the Sheet already carries it as real
data, the same as any other column.

The whole tab (like Finance and Inventory) is filtered upstream in
app.py by the Consolidated/USA/Nigeria entity selector — this file has
no awareness of that filter beyond already receiving a pre-filtered
sales_df/finance_df; `entity` is passed through only for chart labeling.
"""

import math

import altair as alt
import pandas as pd
import streamlit as st

from styling import PRODUCT_COLORS, CLIENT_TYPE_COLORS, WIN_LOSS_COLORS, NAVY, AMBER, TEXT_SECONDARY, BORDER

GOAL_COLOR = BORDER
# The one color for any on-chart number that sits inside a dark bar fill
# (navy actual bars, the Win/Loss bars, etc.) — grey (TEXT_SECONDARY) reads
# fine on the white page background but is low-contrast on a dark fill,
# which is what made the exceeded-case goal label (sitting inside the
# taller actual bar) hard to read. Every such label uses this same white,
# consistently, rather than each mark picking its own shade.
LABEL_ON_DARK_COLOR = "#F7F8FA"


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
    # Two labels, positioned differently depending on which bar is taller —
    # used by both Sales YTD and Sales by Quarter (Tatiana flagged this on
    # the Quarter panel, but the rule is general to any goal-vs-actual bar):
    #   - Normal case (goal >= actual, the common case): goal sits OUTSIDE
    #     the bar, nudged above its own top — dy=-10 already does this
    #     since goal_label_y is the goal value itself. Actual sits INSIDE
    #     its own bar, vertically centered, well clear of the goal label
    #     above it.
    #   - Exceeded case (actual > goal): the goal marker becomes an inline
    #     benchmark INSIDE the taller actual bar, sitting right at the
    #     goal's own true height (still nudged up dy=-10 so it doesn't sit
    #     on top of the bar's fill). The actual/won figure — now the more
    #     important number — moves to the TOP, above the bar it just beat,
    #     the same "nudged outside" treatment goal normally gets.
    # This means goal_label_y is always just the goal value (never
    # max(goal, actual) — an earlier version did that, which floated the
    # goal label up to actual's height in the exceeded case instead of
    # showing where the goal itself actually sits).
    exceeded = df["actual"] > df["goal"]
    df["goal_label_y"] = df["goal"]
    df["actual_label_y"] = df["actual"].where(exceeded, other=df["actual"] * 0.5)
    df["actual_inside_bar"] = ~exceeded
    # Whichever label currently sits INSIDE the dark actual bar gets
    # LABEL_ON_DARK_COLOR; whichever sits OUTSIDE, on the page background,
    # gets TEXT_SECONDARY. Normal case: actual is inside (white), goal is
    # outside (grey). Exceeded case: that flips — goal is now the one
    # inline inside the taller actual bar (white), and actual moved
    # outside, above the bar it beat (grey). actual==0 is a special case
    # of "outside" — there's no bar at all for the label to sit inside.
    df["actual_label_color"] = df.apply(
        lambda r: (TEXT_SECONDARY if (r["actual"] == 0 or r["actual"] > r["goal"]) else LABEL_ON_DARK_COLOR), axis=1)
    df["goal_label_color"] = exceeded.map({True: LABEL_ON_DARK_COLOR, False: TEXT_SECONDARY})

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
    goal_labels = base.mark_text(dy=-10, fontWeight="bold", fontSize=11).encode(
        x=alt.X(f"{x_field}:N", sort=x_sort), y=alt.Y("goal_label_y:Q", scale=y_scale), text=alt.Text("goal_label:N"),
        color=alt.Color("goal_label_color:N", scale=None, legend=None),
        tooltip=tooltip,
    )
    # Split into two layers rather than one, because the two cases need a
    # different dy (pixel nudge) — dy is a fixed mark property in
    # Vega-Lite, not something that can vary per row within one mark, so
    # "centered inside the bar" (dy=0) and "nudged above the bar" (dy=-10,
    # same treatment as goal_label) each need their own mark_text call.
    actual_labels_inside = base.transform_filter(alt.datum.actual_inside_bar).mark_text(
        fontWeight="bold", fontSize=11,
    ).encode(
        x=alt.X(f"{x_field}:N", sort=x_sort), y=alt.Y("actual_label_y:Q", scale=y_scale), text=alt.Text("actual_label:N"),
        color=alt.Color("actual_label_color:N", scale=None, legend=None),
        tooltip=tooltip,
    )
    actual_labels_outside = base.transform_filter(~alt.datum.actual_inside_bar).mark_text(
        dy=-10, fontWeight="bold", fontSize=11,
    ).encode(
        x=alt.X(f"{x_field}:N", sort=x_sort), y=alt.Y("actual_label_y:Q", scale=y_scale), text=alt.Text("actual_label:N"),
        color=alt.Color("actual_label_color:N", scale=None, legend=None),
        tooltip=tooltip,
    )
    return (goal_bars + actual_bars + goal_labels + actual_labels_inside + actual_labels_outside).properties(height=height)


def gauge_chart(pct, actual, target, color, title, height=190):
    """Semicircular gauge — a "value" arc over a light grey "remainder"
    track, both stacked into a half-circle by giving theta's scale a
    [-π/2, π/2] range instead of the usual full-circle [0, 2π]. Same
    stacking mechanics as a donut chart (two wedges that sum to the whole),
    just rotated into a dome instead of a full circle.

    Visually capped at 100% (a >100% gauge would otherwise wrap back past
    the dome and look broken), but the printed percentage is never capped
    — the shape can only ever undersell an over-target channel, never
    overstate an underperforming one.
    """
    pct_capped = max(0.0, min(pct, 1.0))
    df = pd.DataFrame([
        {"segment": "value", "amount": pct_capped, "order": 0},
        {"segment": "remainder", "amount": 1 - pct_capped, "order": 1},
    ])
    # Both segments carry the same real (uncapped) figures, so hovering
    # the grey remainder wedge shows the same useful tooltip as the
    # colored value wedge — same reasoning as bullet_chart's shared
    # tooltip on every layer.
    df["channel"], df["actual"], df["target"], df["pct"] = title, actual, target, pct
    df["pct_label"], df["title_label"] = f"{pct:.0%}", title
    df["min_label"], df["max_label"] = "0%", "100%"
    tooltip = [
        alt.Tooltip("channel:N", title="Channel"),
        alt.Tooltip("actual:Q", title="Actual (YTD)", format="$,.0f"),
        alt.Tooltip("target:Q", title="Target", format="$,.0f"),
        alt.Tooltip("pct:Q", title="% of Target", format=".0%"),
    ]
    # One shared `base`/dataset for all three layers (arc + both text
    # labels), same as bullet_chart and the Sales by Channel pie —
    # layering in separate single-row alt.Chart(...) objects for the text
    # (each its own tiny dataset) intermittently rendered as a BLANK gauge
    # after switching entities: Streamlit tries to patch an existing
    # chart's Vega view in place across a rerun, and with 3 different
    # datasets in one spec that patch could silently fail (a console
    # "Unrecognized data set" error, no visible error in the UI, empty
    # arc/text marks). A single shared dataset — filtered down to one row
    # for the text layers via transform_filter, the same technique
    # actual_labels_inside/outside above use — doesn't trigger it.
    base = alt.Chart(df)
    arc = base.mark_arc(innerRadius=64, outerRadius=95, cornerRadius=6).encode(
        theta=alt.Theta("amount:Q", stack=True, scale=alt.Scale(domain=[0, 1], range=[-math.pi / 2, math.pi / 2])),
        color=alt.Color("segment:N", scale=alt.Scale(domain=["value", "remainder"], range=[color, BORDER]), legend=None),
        order=alt.Order("order:N"),
        tooltip=tooltip,
    )
    pct_text = base.transform_filter(alt.datum.segment == "value").mark_text(
        fontSize=26, fontWeight="bold", color=NAVY, dy=-8,
    ).encode(text="pct_label:N", tooltip=tooltip)
    title_text = base.transform_filter(alt.datum.segment == "value").mark_text(
        fontSize=14, fontWeight="bold", color=TEXT_SECONDARY, dy=14,
    ).encode(text="title_label:N", tooltip=tooltip)
    # Scale endpoints, right at the two tips of the dome (the arc's left
    # tip is 0% and right tip is 100% by construction — that's what the
    # theta scale's [-π/2, π/2] range means) — dx/dy nudge them just
    # outside the arc rather than on top of its stroke. tooltip=alt.value(None)
    # turns the tooltip off entirely for these two — without it, hovering
    # falls back to Altair's default raw-field dump (same issue fixed
    # earlier on the bullet charts' labels), but these are just static
    # scale markers, not data worth a tooltip at all.
    min_text = base.transform_filter(alt.datum.segment == "value").mark_text(
        fontSize=12, color=TEXT_SECONDARY, dx=-103, dy=10,
    ).encode(text="min_label:N", tooltip=alt.value(None))
    max_text = base.transform_filter(alt.datum.segment == "value").mark_text(
        fontSize=12, color=TEXT_SECONDARY, dx=103, dy=10,
    ).encode(text="max_label:N", tooltip=alt.value(None))
    return (arc + pct_text + title_text + min_text + max_text).properties(height=height)


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

    with row2_left, st.container(border=True):
        st.markdown("**Sales by Channel**")
        by_client_type = won_ytd.groupby("client_type").deal_value.sum().reindex(list(CLIENT_TYPE_COLORS)).reset_index()
        by_client_type.columns = ["client_type", "revenue"]
        by_client_type["revenue"] = by_client_type["revenue"].fillna(0)
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

        # Channel targets, gauges below the pie in the SAME bordered
        # container — that's what ties them together as one panel to
        # read, rather than the gauges looking like an unrelated chart
        # that happens to sit nearby. Targets come from the Finance tab's
        # budget_institutional_revenue/budget_commercial_revenue (summed
        # over the year, same "sum the monthly column" pattern as every
        # other annual target on this tab), which in turn trace back to
        # the Assumptions tab's Channel Revenue Target Split — not
        # invented here.
        channel_target = finance_df[finance_df.month.str.startswith(str(year))][
            ["budget_institutional_revenue", "budget_commercial_revenue"]].sum()
        target_institutional = channel_target["budget_institutional_revenue"]
        target_commercial = channel_target["budget_commercial_revenue"]
        actual_by_channel = by_client_type.set_index("client_type").revenue
        actual_institutional = actual_by_channel.get("Institutional", 0)
        actual_commercial = actual_by_channel.get("Commercial", 0)

        # key= includes the rounded value, not just the entity — Streamlit
        # otherwise sometimes tries to patch an existing gauge's Vega view
        # in place across a rerun rather than fully remounting it, and that
        # patch can fail silently (an "Unrecognized data set" console
        # error, empty arc/text marks with no visible error in the UI).
        # Keying on the value itself forces a clean remount whenever the
        # numbers actually change, instead of patching.
        #
        # Stacked one per row (full container width, ~300px) rather than
        # side by side — side by side only gave each gauge ~145px to work
        # with, forcing a radius so small it looked out of place next to
        # every other chart on this tab. Full width lets the radius match
        # the pie chart directly above instead.
        pct_institutional = (actual_institutional / target_institutional) if target_institutional else 0
        st.altair_chart(
            gauge_chart(pct_institutional, actual_institutional, target_institutional, NAVY, "Institutional"),
            use_container_width=True, key=f"gauge_institutional_{entity}_{pct_institutional:.4f}",
        )
        pct_commercial = (actual_commercial / target_commercial) if target_commercial else 0
        st.altair_chart(
            gauge_chart(pct_commercial, actual_commercial, target_commercial, AMBER, "Commercial"),
            use_container_width=True, key=f"gauge_commercial_{entity}_{pct_commercial:.4f}",
        )

    with row2_right:
        st.markdown("**Win/Loss Rate YTD**")
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
        # fontSize=11 and TEXT_SECONDARY, matching every other on-chart
        # label on this tab (bullet chart goals, pie percentages, forecast
        # totals) — this one used to be fontSize=12 with no color set
        # (defaulting to black), the only label on the whole page that
        # didn't match the rest.
        wl_labels = alt.Chart(wl_df).mark_text(
            fontWeight="bold", fontSize=11, color=TEXT_SECONDARY, dy=alt.expr("datum.pct > 0 ? -8 : 14"),
        ).encode(
            x=alt.X("label:N"), y=alt.Y("pct:Q"), text=alt.Text("pct:Q", format=".0%"), tooltip=wl_tooltip,
        )
        st.altair_chart((wl_chart + wl_labels).properties(height=260), use_container_width=True)

    st.divider()

    # --- Pipeline -----------------------------------------------------------
    st.subheader("Pipeline")

    # Forecast data (used by the chart further down) is built here, before
    # the scorecards, just so the whole Pipeline section reads top to
    # bottom in the order things are computed.
    #
    # Starts at the CURRENT month, not Jan 1 — a forecast should look
    # ahead, not dwell on months that have already happened. This means
    # the window naturally shrinks as the year goes on (5 months left in
    # August, 1 month left in December) rather than always showing 12.
    # open_deals' expected_close_date is always today-or-later by
    # construction, so open_grouped already only ever has current-month-
    # forward entries; won_grouped can have earlier months too (deals
    # actually won back in January, say), which is exactly why the loop
    # below only pulls from forecast_months rather than summing the whole
    # year — that keeps prior months' Won revenue out of the chart.
    forecast_months = pd.date_range(f"{year}-{as_of.month:02d}-01", f"{year}-12-01", freq="MS")
    current_month_label = forecast_months[0].strftime("%b %Y")

    open_by_month = open_deals.copy()
    open_by_month["month"] = open_by_month.expected_close_date.dt.to_period("M").dt.to_timestamp()
    open_grouped = open_by_month[open_by_month.month.dt.year == year].groupby("month").weighted_value.sum()

    won_by_month = won_deals.copy()
    won_by_month["month"] = won_by_month.actual_close_date.dt.to_period("M").dt.to_timestamp()
    won_grouped = won_by_month[won_by_month.month.dt.year == year].groupby("month").weighted_value.sum()

    forecast_rows = []
    for m in forecast_months:
        label = m.strftime("%b %Y")
        won_so_far = won_grouped.get(m, 0.0)
        # Only the current month's rows carry this note — it's there so
        # that hovering the current month's bar (whichever segment, Open
        # or Won) surfaces how much of it is already booked, since that's
        # the one month where "Open" and "Won" both show up stacked
        # together. Other months get a blank note; Altair can't omit a
        # tooltip row per-datum, only show it with an empty value.
        note = f"{money_label(won_so_far)} already won" if label == current_month_label else ""
        forecast_rows.append({"month": label, "month_sort": m, "series": "Open",
                               "value": open_grouped.get(m, 0.0), "note": note})
        forecast_rows.append({"month": label, "month_sort": m, "series": "Won", "value": won_so_far, "note": note})
    forecast_df = pd.DataFrame(forecast_rows)
    month_order = [m.strftime("%b %Y") for m in forecast_months]
    forecast_colors = {"Open": PRODUCT_COLORS["Sol 1"], "Won": NAVY}

    col1, col2, col3, col4 = st.columns(4)
    annual_target = finance_df[finance_df.month.str.startswith(str(year))].budget_revenue.sum()
    weighted_pipeline = open_deals.weighted_value.sum()
    # Named "Revenue Forecast / Weighted Pipeline" rather than having two
    # separate scorecards — a standalone "Revenue Forecast" number that
    # quietly folded in this month's already-Won revenue read as a
    # forward-looking forecast while actually mixing in the past, which
    # was confusing. This is just the open pipeline, weighted by
    # probability — the only genuinely forward-looking total.
    col1.metric("Revenue Forecast / Weighted Pipeline", f"${weighted_pipeline:,.0f}",
                f"{weighted_pipeline/annual_target:.0%} of annual target" if annual_target else None,
                delta_color="off")

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

    # No xOffset here — with only one of the two series usually non-zero
    # in a given month (Won for months already closed, Open for months
    # still ahead), an xOffset grouped-bar layout put the one visible bar
    # at the 1/4 or 3/4 mark of its month's slot instead of centered under
    # the tick label, which is what looked "off-centered." Both series
    # share the same x position instead, which is also what makes them
    # stack (the current month shows Won stacked under Open, since it's
    # the one month with real numbers in both).
    forecast_tooltip = [alt.Tooltip("month:N", title="Month"), alt.Tooltip("series:N", title="Status"),
                         alt.Tooltip("value:Q", title="Weighted Value", format="$,.0f"),
                         alt.Tooltip("note:N", title="Note")]
    forecast_chart = alt.Chart(forecast_df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=36).encode(
        x=alt.X("month:N", title=None, sort=month_order, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("value:Q", title="Weighted Value ($)", axis=alt.Axis(labelExpr=MONEY_AXIS_EXPR)),
        color=alt.Color("series:N", title=None, scale=alt.Scale(
            domain=["Open", "Won"], range=[forecast_colors["Open"], forecast_colors["Won"]]),
            legend=alt.Legend(orient="bottom", symbolType="circle")),
        tooltip=forecast_tooltip,
    )
    # One label per month showing the TOTAL (Open + Won stacked height),
    # from a separate month-level dataframe — the per-series rows above
    # don't carry a "total" field, and Vega-Lite's automatic bar stacking
    # doesn't expose the stacked sum back to a text mark on its own.
    totals_df = forecast_df.groupby(["month", "month_sort"], as_index=False).value.sum()
    totals_df["label"] = totals_df.value.apply(money_label)
    total_labels = alt.Chart(totals_df).mark_text(dy=-8, fontWeight="bold", fontSize=11, color=TEXT_SECONDARY).encode(
        x=alt.X("month:N", sort=month_order),
        y=alt.Y("value:Q"),
        text=alt.Text("label:N"),
        tooltip=[alt.Tooltip("month:N", title="Month"), alt.Tooltip("value:Q", title="Total", format="$,.0f")],
    )
    st.altair_chart((forecast_chart + total_labels).properties(height=280), use_container_width=True)

    st.divider()
    st.markdown("**Open Pipeline — Detail**")
    display_cols = ["deal_id", "subsidiary", "buyer_type", "client_type", "buyer_name", "product",
                     "deal_value", "stage", "probability", "weighted_value", "expected_close_date"]
    st.dataframe(
        open_deals[display_cols].sort_values("expected_close_date"),
        use_container_width=True, hide_index=True,
        column_config={
            # Labels only — the underlying column names (subsidiary,
            # buyer_type, etc.) stay as-is, since those same names are
            # relied on for filtering/joins elsewhere in Sales, Finance,
            # and Inventory (e.g. Inventory's reorder alert filters on
            # open_deals["product"]). Renaming the real columns would mean
            # updating the generator scripts, the Google Sheet, and every
            # tab that reads them — this table is a display-only concern.
            "deal_id": st.column_config.TextColumn("Deal ID"),
            "subsidiary": st.column_config.TextColumn("Entity"),
            "buyer_type": st.column_config.TextColumn("Customer Category"),
            "client_type": st.column_config.TextColumn("Channel"),
            "buyer_name": st.column_config.TextColumn("Customer"),
            "product": st.column_config.TextColumn("Product"),
            "stage": st.column_config.TextColumn("Pipeline Stage"),
            # format="$%,.0f" LOOKS right but silently fails in this
            # Streamlit version — the "," thousands-separator flag isn't
            # supported by its printf-style formatter (sprintf.js), so it
            # falls back to showing the raw unformatted number. The
            # predefined "dollar" preset does support commas; pairing it
            # with step=1 is what drops it to 0 decimals (dollar's default
            # is 2) — confirmed empirically, since this isn't documented.
            "deal_value": st.column_config.NumberColumn("Deal Value", format="dollar", step=1),
            # Same story for percent: the printf spec "%.0f%%" doesn't
            # multiply the underlying 0-1 fraction by 100 (it would show
            # "1%" for 0.9), but the predefined "percent" preset does.
            "probability": st.column_config.NumberColumn("Probability", format="percent"),
            "weighted_value": st.column_config.NumberColumn("Weighted Value", format="dollar", step=1),
            "expected_close_date": st.column_config.DateColumn("Expected Close"),
        },
    )
