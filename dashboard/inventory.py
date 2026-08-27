"""
Inventory pillar: stock on hand, by product and warehouse, and reorder
alerts that factor in weighted open-pipeline demand — not just static
stock levels. This is the one KPI the spec explicitly calls out as
deliberately connecting two pillars instead of treating them separately.

The logic, in plain English:

A static reorder point (already in the Inventory tab) asks "is today's
stock below the safety threshold?" That misses a real risk: a big,
near-certain deal about to close can wipe out stock that looks perfectly
healthy today. So for each product/warehouse, this pulls every OPEN deal
in the Sales tab for that product/subsidiary EXPECTED TO CLOSE WITHIN
REORDER_LOOKAHEAD_MONTHS (1 month, matching the lead-time assumption
behind reorder_point itself), and asks "if these near-term deals close
roughly as expected, weighted by how likely each one is, how many units
would that actually take off the shelf?" A deal that's 8 months out
doesn't count — there's plenty of time for a normal restock before it
could possibly close, so it shouldn't trigger an urgent alert today.

    pipeline_demand_units = sum(weighted_value for open deals of this
                                 product/subsidiary) / that product's unit price

    projected_stock = stock_on_hand - pipeline_demand_units

Then three tiers, matching the brand guide's status colors:
    RED (Critical)  — already below the static reorder point right now,
                       OR the pipeline alone would wipe it out (projected < 0)
    AMBER (Warning) — fine today, but pipeline demand would push it below
                       the safety threshold (projected < reorder_point)
    GREEN (Healthy) — comfortably covers today's threshold AND the pipeline

That's what lets a big open deal flip a row from green to amber/red even
though nothing about today's stock count changed.

A separate "Sales in Fulfillment" table at the bottom lists Closed Won
deals whose delivery_status (on the AR tab) is still "Open" — not yet
delivered. This is intentionally NOT netted against stock_on_hand above:
Tatiana's call, this tab means on-hand stock, full stop, not stock net
of in-flight commitments the way a real fulfillment system (e.g. SOS)
would track it — that level of detail belongs to Ops, not this view.
"""

import altair as alt
import pandas as pd
import streamlit as st

from styling import PRODUCT_COLORS, STATUS_GOOD, STATUS_WARNING, STATUS_CRITICAL, NAVY, TEXT_SECONDARY

# Only deals expected to close within this window count as "pipeline
# demand" for the alert — a deal that's 8 months out shouldn't trigger a
# reorder flag today; there's plenty of time for a normal restock before
# it could possibly close. This should match AVG_LEAD_TIME_MONTHS in
# scripts/config.py (the assumption behind reorder_point itself) — both
# represent "how much runway before we'd need to act." It's a judgment
# call duplicated here rather than read from the Sheet, since lead time
# itself isn't stored as data anywhere in the Inventory tab, only its
# result (reorder_point) is.
REORDER_LOOKAHEAD_MONTHS = 1


def compute_reorder_status(inventory_df, sales_df, as_of):
    lookahead_cutoff = as_of + pd.DateOffset(months=REORDER_LOOKAHEAD_MONTHS)
    open_deals = sales_df[(sales_df.status == "Open") & (sales_df.expected_close_date <= lookahead_cutoff)]

    # Unit price per product, read from the Sales data itself (not
    # hardcoded here) — keeps this file honoring the "dashboard reads
    # only from the Sheet" rule, same principle as the Sales tab's target.
    unit_price = sales_df.groupby("product").unit_price.first()

    rows = []
    for _, row in inventory_df.iterrows():
        product, subsidiary = row["product"], row["subsidiary"]
        # NOTE: must use open_deals["product"], not open_deals.product —
        # pandas DataFrames have a built-in .product() method (computes a
        # product of values) that silently shadows attribute access to a
        # column actually named "product". Using .product here would
        # compare that bound method object to a string, always False —
        # meaning pipeline would always be empty and this entire
        # pipeline-aware calculation would silently compute zero demand
        # for every row, no matter what's actually in the open pipeline.
        pipeline = open_deals[(open_deals["product"] == product) & (open_deals["subsidiary"] == subsidiary)]
        pipeline_weighted_value = pipeline.weighted_value.sum()
        pipeline_demand_units = pipeline_weighted_value / unit_price.get(product, row["stock_on_hand"] or 1)

        projected_stock = row["stock_on_hand"] - pipeline_demand_units

        if row["stock_on_hand"] < row["reorder_point"] or projected_stock < 0:
            status = "Critical"
        elif projected_stock < row["reorder_point"]:
            status = "Warning"
        else:
            status = "Healthy"

        rows.append({
            **row.to_dict(),
            "pipeline_demand_units": round(pipeline_demand_units, 1),
            "projected_stock": round(projected_stock, 1),
            "reorder_status": status,
        })
    return pd.DataFrame(rows)


def render(sales_df, inventory_df, ar_df, as_of):
    inv = compute_reorder_status(inventory_df, sales_df, as_of)

    st.subheader("Stock & Reorder Status")
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Available Stock", f"{inv.stock_on_hand.sum():,.0f}")
    critical = (inv.reorder_status == "Critical").sum()
    warning = (inv.reorder_status == "Warning").sum()
    col2.metric("Critical (reorder now)", critical)
    col3.metric("Warning (pipeline risk)", warning)
    col4.metric("Healthy", (inv.reorder_status == "Healthy").sum())

    st.divider()

    left, right = st.columns([3, 2])

    STATUS_COLOR = {"Healthy": STATUS_GOOD, "Warning": STATUS_WARNING, "Critical": STATUS_CRITICAL}

    with left:
        st.markdown("**Stock on Hand vs. Reorder Point, by Product & Warehouse**")
        chart_df = inv.copy()
        # City only ("Houston", not "Houston, TX") — the state/country
        # suffix wasn't adding anything a reader needed to tell the two
        # warehouses apart, just extra width on an axis that's already
        # tight with 10 rows.
        chart_df["label"] = chart_df["product"] + " — " + chart_df["warehouse"].str.split(",").str[0]
        bars = alt.Chart(chart_df).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=18).encode(
            y=alt.Y("label:N", title=None, sort=alt.SortField("product")),
            x=alt.X("stock_on_hand:Q", title="Units"),
            color=alt.Color("reorder_status:N", title="Status", scale=alt.Scale(
                domain=list(STATUS_COLOR), range=list(STATUS_COLOR.values()))),
            tooltip=[alt.Tooltip("label:N", title="Product / Warehouse"),
                     alt.Tooltip("stock_on_hand:Q", title="Stock on Hand", format=",.0f"),
                     alt.Tooltip("reorder_point:Q", title="Reorder Point", format=",.0f"),
                     alt.Tooltip("projected_stock:Q", title="Projected (after pipeline)", format=",.0f"),
                     alt.Tooltip("reorder_status:N", title="Status")],
        )
        ticks = alt.Chart(chart_df).mark_tick(color=NAVY, thickness=2, size=22).encode(
            y=alt.Y("label:N", sort=alt.SortField("product")),
            x=alt.X("reorder_point:Q"),
        )
        st.altair_chart((bars + ticks).properties(height=320), use_container_width=True)
        st.caption("Navy tick marks show each row's static reorder point.")

    with right:
        st.markdown("**Total Units by Product**")
        by_product = inv.groupby("product", as_index=False).stock_on_hand.sum().set_index("product").reindex(list(PRODUCT_COLORS)).reset_index()
        chart = alt.Chart(by_product).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=32).encode(
            x=alt.X("product:N", title=None, sort=list(PRODUCT_COLORS), axis=alt.Axis(labelAngle=0)),
            y=alt.Y("stock_on_hand:Q", title="Units"),
            color=alt.Color("product:N", scale=alt.Scale(
                domain=list(PRODUCT_COLORS), range=list(PRODUCT_COLORS.values())), legend=None),
            tooltip=[alt.Tooltip("product:N", title="Product"), alt.Tooltip("stock_on_hand:Q", title="Units", format=",.0f")],
        ).properties(height=320)
        st.altair_chart(chart, use_container_width=True)

    st.divider()
    st.markdown("**Detail — Stock, Pipeline Demand & Reorder Status**")
    display_cols = ["warehouse", "product", "stock_on_hand", "reorder_point",
                     "pipeline_demand_units", "projected_stock", "reorder_status"]
    st.dataframe(
        inv[display_cols].sort_values(["reorder_status", "product"]),
        use_container_width=True, hide_index=True,
        column_config={
            "warehouse": "Warehouse", "product": "Product",
            # format="%,.0f" LOOKS right but silently fails in this
            # Streamlit version — the "," thousands-separator flag isn't
            # supported by its printf-style formatter (sprintf.js), so it
            # falls back to the raw unformatted number. The predefined
            # "localized" preset does support commas (confirmed
            # empirically, since this isn't documented).
            "stock_on_hand": st.column_config.NumberColumn("Stock on Hand", format="localized"),
            "reorder_point": st.column_config.NumberColumn("Reorder Point", format="localized"),
            "pipeline_demand_units": st.column_config.NumberColumn("Weighted Pipeline Demand", format="localized"),
            "projected_stock": st.column_config.NumberColumn("Projected Stock", format="localized"),
            "reorder_status": "Status",
        },
    )

    st.divider()
    st.markdown("**Sales in Fulfillment**")
    st.caption("Closed Won deals not yet delivered — delivery_status on the AR tab, separate from payment status.")
    in_fulfillment = ar_df[ar_df.delivery_status == "Open"].sort_values("actual_close_date")

    ful_col1, ful_col2 = st.columns(2)
    ful_col1.metric("Deals in Fulfillment", f"{len(in_fulfillment):,}")
    ful_col2.metric("Value in Fulfillment", f"${in_fulfillment.amount.sum():,.0f}")

    ful_display_cols = ["invoice_id", "subsidiary", "buyer_type", "buyer_name", "product",
                         "amount", "actual_close_date"]
    st.dataframe(
        in_fulfillment[ful_display_cols],
        use_container_width=True, hide_index=True,
        column_config={
            "invoice_id": st.column_config.TextColumn("Invoice ID"),
            "subsidiary": st.column_config.TextColumn("Entity"),
            "buyer_type": st.column_config.TextColumn("Customer Category"),
            "buyer_name": st.column_config.TextColumn("Customer"),
            "product": st.column_config.TextColumn("Product"),
            "amount": st.column_config.NumberColumn("Amount", format="dollar", step=1),
            "actual_close_date": st.column_config.DateColumn("Closed On"),
        },
    )
