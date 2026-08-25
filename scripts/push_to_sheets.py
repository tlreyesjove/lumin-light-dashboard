"""
Pushes the generated CSVs in /data into a Google Sheet, one tab per pillar
(Sales, Finance, Inventory) — overwriting whatever was there before.

This is the piece that plays the role a real Zapier automation would play
in production: something writing fresh data into the Sheet that the
dashboard reads from. Run generate_data.py first so /data is up to date.

Requires (see README for the one-time setup):
- A Google Sheet already created, shared with your service account's
  email address as an Editor.
- GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_FILE set in .env.

Usage:
    python3 push_to_sheets.py
"""

import os
import sys

import gspread
import pandas as pd
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

TABS = {
    "Sales": "sales.csv",
    "Finance": "finance.csv",
    "Inventory": "inventory.csv",
}


def get_client():
    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not key_path or not os.path.exists(key_path):
        sys.exit(
            f"Can't find the service account key file at '{key_path}'.\n"
            "Check GOOGLE_SERVICE_ACCOUNT_FILE in your .env file, and that "
            "the JSON file is actually there."
        )
    creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return gspread.authorize(creds)


def push_tab(spreadsheet, tab_name, csv_filename):
    csv_path = os.path.join(DATA_DIR, csv_filename)
    if not os.path.exists(csv_path):
        sys.exit(f"Missing {csv_path} — run generate_data.py first.")

    df = pd.read_csv(csv_path)

    try:
        worksheet = spreadsheet.worksheet(tab_name)
        worksheet.clear()
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=len(df) + 10, cols=len(df.columns) + 2)

    values = [df.columns.tolist()] + df.astype(object).where(pd.notnull(df), "").values.tolist()
    worksheet.update(values, value_input_option="RAW")
    print(f"  {tab_name}: wrote {len(df)} rows")


def main():
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        sys.exit("GOOGLE_SHEET_ID is not set. Copy .env.example to .env and fill it in.")

    client = get_client()
    try:
        spreadsheet = client.open_by_key(sheet_id)
    except gspread.exceptions.SpreadsheetNotFound:
        sys.exit(
            "Google Sheet not found (or not shared with the service account).\n"
            "Check GOOGLE_SHEET_ID in .env, and that the Sheet is shared with "
            "your service account's email as an Editor."
        )

    print(f"Writing to: {spreadsheet.title} ({spreadsheet.url})")
    for tab_name, csv_filename in TABS.items():
        push_tab(spreadsheet, tab_name, csv_filename)

    print("\nDone.")


if __name__ == "__main__":
    main()
