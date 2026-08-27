# Lumin Light — Leadership Dashboard

Personal portfolio project: a synthetic-data leadership dashboard for a fictional
B2B solar lighting company. See `Lumin Light Project Spec.md` for the full plan.

**Status: Phase 1 — synthetic data generation.** (Streamlit dashboard is Phase 3, not built yet.)

## What's here so far

- `scripts/config.py` — every assumption the data is built from (revenue targets,
  product pricing, deal size ranges, etc.) in one place.
- `scripts/generate_sales.py`, `generate_finance.py`, `generate_inventory.py` — one
  generator per dashboard pillar.
- `scripts/generate_data.py` — runs all three, writes CSVs to `/data`.
- `scripts/push_to_sheets.py` — pushes those CSVs into a Google Sheet (one tab per
  pillar), the way a real Zapier automation would in production.

## Running it

```bash
source .venv/bin/activate
python3 scripts/generate_data.py
```

This regenerates `data/sales.csv`, `data/finance.csv`, `data/inventory.csv`. Re-run
any time you change a number in `config.py`.

## One-time setup: connecting to Google Sheets

This lets the script above write straight into a Google Sheet, instead of you
copy-pasting CSVs by hand. You do this part yourself (Claude Code doesn't sign
into your Google account) — takes about 10 minutes, one time only.

**1. Create the Google Sheet**
- Go to [sheets.google.com](https://sheets.google.com), create a new blank sheet.
- Name it something like "Lumin Light Data".
- Copy the long ID from its URL: `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

**2. Create a Google Cloud project**
- Go to [console.cloud.google.com](https://console.cloud.google.com).
- Top-left project dropdown → **New Project**. Name it "Lumin Light Dashboard" → Create.
- Make sure that new project is selected (top-left dropdown).

**3. Enable the Google Sheets API**
- In the search bar at the top, search "Google Sheets API" → open it → click **Enable**.

**4. Create a service account** (this is the "robot login" the script uses)
- Search "Service Accounts" in the top search bar → **Create Service Account**.
- Name: `lumin-light-sheets-writer` → Create and Continue → skip the optional
  role/access screens → Done.
- Click on the service account you just created → **Keys** tab → **Add Key** →
  **Create new key** → type **JSON** → Create. A `.json` file downloads.
- Move that downloaded file into this project's `credentials/` folder, and
  rename it to `service_account.json`.

**5. Share the Sheet with the service account**
- Open the service account's details page (Cloud Console → Service Accounts) and
  copy its email address — looks like
  `lumin-light-sheets-writer@your-project-id.iam.gserviceaccount.com`.
- Open your Google Sheet from step 1 → **Share** → paste that email → give it
  **Editor** access → Send (it's fine that it's not a real person's email).

**6. Fill in your local config**
- Copy `.env.example` to a new file named `.env` in the project root.
- Paste your Sheet ID from step 1 into `GOOGLE_SHEET_ID`.
- Leave `GOOGLE_SERVICE_ACCOUNT_FILE` as-is if you followed step 4 exactly.

**7. Push the data**
```bash
source .venv/bin/activate
python3 scripts/push_to_sheets.py
```

You should see four tabs appear in your Google Sheet: Sales, Finance, Inventory, AR.

Both `.env` and `credentials/service_account.json` are gitignored — they never
get committed, since they're specific to your Google account.
