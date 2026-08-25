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

st.set_page_config(page_title="Lumin Light Dashboard", page_icon="☀️", layout="wide")
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

sales_df, finance_df, inventory_df = data["sales"], data["finance"], data["inventory"]
as_of = pd.to_datetime(inventory_df["as_of_date"].max())

render_header(f"Data as of {as_of.strftime('%B %-d, %Y')}")

tab_sales, tab_finance, tab_inventory = st.tabs(["📈 Sales", "💰 Finance", "📦 Inventory"])

with tab_sales:
    sales_page.render(sales_df, finance_df, as_of)

with tab_finance:
    finance_page.render(sales_df, finance_df, as_of)

with tab_inventory:
    inventory_page.render(sales_df, inventory_df, as_of)
