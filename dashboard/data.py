"""
Connects to the Google Sheet and loads the three pillar tabs into DataFrames.

Two different kinds of caching are at play here, and they're deliberately
separate:

- The Google connection itself (st.cache_resource) — expensive to set up,
  safe to reuse across every page load. Never needs to expire.
- The actual DATA (st.cache_data) — this is what the "Refresh" button
  clears. Without a manual refresh, Streamlit would just keep serving the
  same cached data forever, so the app would never show a newly-updated
  Sheet without a full restart.
"""

import os
import streamlit as st
import gspread
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
TABS = ["Sales", "Finance", "Inventory"]


@st.cache_resource
def get_client():
    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_data
def load_data():
    client = get_client()
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    spreadsheet = client.open_by_key(sheet_id)

    data = {}
    for tab in TABS:
        worksheet = spreadsheet.worksheet(tab)
        records = worksheet.get_all_records()
        data[tab.lower()] = pd.DataFrame(records)

    # Numeric/date columns come back from Sheets as strings — restore types.
    sales = data["sales"]
    for col in ["quantity", "unit_price", "unit_cost", "deal_value", "probability", "weighted_value"]:
        sales[col] = pd.to_numeric(sales[col], errors="coerce")
    for col in ["created_date", "expected_close_date"]:
        sales[col] = pd.to_datetime(sales[col], errors="coerce")
    sales["actual_close_date"] = pd.to_datetime(sales["actual_close_date"], errors="coerce")

    finance = data["finance"]
    for col in ["revenue", "cogs", "opex", "ebit", "budget_revenue", "budget_ebit",
                "net_cash_change", "cash_balance"]:
        finance[col] = pd.to_numeric(finance[col], errors="coerce")

    inventory = data["inventory"]
    for col in ["stock_on_hand", "avg_monthly_demand_units", "max_monthly_demand_units",
                "safety_stock", "reorder_point"]:
        inventory[col] = pd.to_numeric(inventory[col], errors="coerce")

    return {"sales": sales, "finance": finance, "inventory": inventory}


def refresh():
    """Clears the data cache (not the connection) so the next load_data()
    call re-pulls from the Sheet instead of serving stale cached results."""
    load_data.clear()
