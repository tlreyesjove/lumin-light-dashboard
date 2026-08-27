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
TABS = ["Sales", "Finance", "Inventory", "AR"]


def _local_secrets():
    """Streamlit's own st.secrets, or {} if none is configured. st.secrets
    is lazy — merely referencing it doesn't raise, it only actually tries
    to find/parse a secrets.toml the moment something queries it (`in`,
    indexing, .get()). So catching the "no secrets file" error means
    forcing that lookup INSIDE the try (dict(...) iterates it fully),
    not just wrapping the bare reference to st.secrets itself."""
    try:
        return dict(st.secrets)
    except Exception:
        return {}


@st.cache_resource
def get_client():
    # Two ways to supply credentials, tried in order:
    # 1. Streamlit's own Secrets — how this works once deployed on
    #    Streamlit Community Cloud, where there's no local file system to
    #    put a JSON key on. The [gcp_service_account] table in Secrets is
    #    just the contents of credentials/service_account.json, pasted in
    #    as TOML instead of JSON.
    # 2. The local .env + credentials/service_account.json file — how
    #    every prior run of this app during development has worked. Left
    #    as the fallback so local development (no secrets.toml at all) is
    #    completely unaffected by this change.
    secrets = _local_secrets()
    if "gcp_service_account" in secrets:
        creds = Credentials.from_service_account_info(dict(secrets["gcp_service_account"]), scopes=SCOPES)
    else:
        key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_data
def load_data():
    client = get_client()
    sheet_id = _local_secrets().get("GOOGLE_SHEET_ID", os.getenv("GOOGLE_SHEET_ID"))
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
    for col in ["revenue", "cogs", "opex", "da", "ebit", "net_income", "budget_revenue", "budget_ebit",
                "budget_opex", "budget_institutional_revenue", "budget_commercial_revenue",
                "net_cash_change", "cash_balance"]:
        finance[col] = pd.to_numeric(finance[col], errors="coerce")

    inventory = data["inventory"]
    for col in ["stock_on_hand", "avg_monthly_demand_units", "max_monthly_demand_units",
                "safety_stock", "reorder_point"]:
        inventory[col] = pd.to_numeric(inventory[col], errors="coerce")

    ar = data["ar"]
    ar["amount"] = pd.to_numeric(ar["amount"], errors="coerce")
    ar["days_overdue"] = pd.to_numeric(ar["days_overdue"], errors="coerce")
    for col in ["actual_close_date", "issue_date", "due_date"]:
        ar[col] = pd.to_datetime(ar[col], errors="coerce")
    # paid_date is genuinely blank for outstanding invoices (Current/Overdue)
    # — errors="coerce" turns that blank string into NaT rather than raising.
    ar["paid_date"] = pd.to_datetime(ar["paid_date"], errors="coerce")

    return {"sales": sales, "finance": finance, "inventory": inventory, "ar": ar}


def refresh():
    """Clears the data cache (not the connection) so the next load_data()
    call re-pulls from the Sheet instead of serving stale cached results."""
    load_data.clear()
