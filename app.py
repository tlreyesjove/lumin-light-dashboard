"""
Lumin Light Leadership Dashboard — Streamlit entry point.

Reads only from the Google Sheet (never from the financial model, or any
source system directly) — that Sheet is the single staging layer this
whole project is built around. "Today" is treated as the data's own
snapshot date (Inventory's as_of_date), not the real system clock — see
the design note in the Learning Doc: this data was generated once, as of
a specific date, and won't silently drift out of sync with itself if the
dashboard is opened weeks or months later.
"""

import sys
import os
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "dashboard"))

from data import load_data, refresh
from styling import inject_css, render_header
import sales as sales_page
import finance as finance_page
import inventory as inventory_page

st.set_page_config(page_title="Lumin Light Dashboard", layout="wide")
inject_css()

top_left, top_right = st.columns([5, 1])
with top_right:
    if st.button("🔄 Refresh", use_container_width=True):
        refresh()
        st.rerun()

try:
    data = load_data()
except Exception as e:
    st.error(
        "Couldn't load data from Google Sheets. Check that `.env` and "
        "`credentials/service_account.json` are set up (see README.md).\n\n"
        f"Details: {e}"
    )
    st.stop()

sales_df, finance_df, inventory_df, ar_df = data["sales"], data["finance"], data["inventory"], data["ar"]
as_of = pd.to_datetime(inventory_df["as_of_date"].max())

render_header(f"Data as of {as_of.strftime('%B %-d, %Y')}")

# Entity selector — one shared control (not repeated per tab) so a choice
# made on one tab carries over to the others. "Lumin Group Consolidated"
# means no filter at all (both subsidiaries combined); the other two
# options filter every dataframe down to just that subsidiary before any
# tab ever sees it, so no per-tab code needs to know the selector exists.
CONSOLIDATED_LABEL = "Lumin Group Consolidated"
# format_func only changes what's shown on the button — the value entity
# gets set to (used below for filtering, and in sales.py for chart titles)
# is still the full "Lumin Light USA" / "Lumin Light Nigeria" string, which
# has to stay as-is because it's what the subsidiary column actually
# contains in the data.
ENTITY_SHORT_LABELS = {"Lumin Light USA": "USA", "Lumin Light Nigeria": "Nigeria"}
entity = st.segmented_control(
    "Entity", options=[CONSOLIDATED_LABEL, "Lumin Light USA", "Lumin Light Nigeria"],
    format_func=lambda e: ENTITY_SHORT_LABELS.get(e, e),
    default=CONSOLIDATED_LABEL, label_visibility="collapsed",
)
entity = entity or CONSOLIDATED_LABEL  # segmented_control can return None if de-selected


def filter_by_entity(df):
    if entity == CONSOLIDATED_LABEL:
        return df
    return df[df.subsidiary == entity]


sales_df, finance_df, inventory_df, ar_df = (
    filter_by_entity(sales_df), filter_by_entity(finance_df), filter_by_entity(inventory_df), filter_by_entity(ar_df)
)

tab_sales, tab_finance, tab_inventory = st.tabs(["Sales", "Finance", "Inventory"])

with tab_sales:
    sales_page.render(sales_df, finance_df, as_of, entity)

with tab_finance:
    finance_page.render(sales_df, finance_df, ar_df, as_of)

with tab_inventory:
    inventory_page.render(sales_df, inventory_df, ar_df, as_of)
