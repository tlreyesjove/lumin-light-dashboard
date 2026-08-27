# Lumin Light Dashboard

A leadership dashboard for **Lumin Light**, a fictional B2B solar lighting
company selling to governments, NGOs, and distributors across US and Nigeria
entities. Built with Python and Streamlit, pulling live data from Google
Sheets to track sales, finance, inventory, and accounts receivable in one
view.

**[View the live dashboard →](https://tlreyesjove-lumin-light-dashboard-app-9zfklp.streamlit.app/)**

This is a personal portfolio project built entirely with synthetic, made-up
data — no connection to any real company's systems or records.

## Features

- **Sales** — pipeline by stage, weighted forecast vs. target, performance by
  product and entity
- **Finance** — revenue vs. budget, gross margin, EBITDA, cash balance
  trend and runway, AR aging
- **Inventory** — stock on hand vs. reorder points, with pipeline-aware
  reorder alerts that flag risk from deals about to close, not just today's
  stock count
- Entity toggle (USA / Nigeria) and manual data refresh throughout

## Tech stack

- **Python** — data generation and transformation (pandas)
- **Streamlit** — the web app itself
- **Altair** — charts
- **Google Sheets API** (via `gspread`) — acts as the live data store, so the
  app behaves like it's reading from a real operational system rather than
  static files

## How it works

Synthetic data is generated locally from a set of assumptions (revenue
targets, pricing, deal sizes, etc.) defined in `scripts/config.py`, then
pushed into a Google Sheet — one tab per pillar (Sales, Finance, Inventory,
AR). The Streamlit app reads from that Sheet on every load, the same way it
would connect to a real company's data source.

```
scripts/config.py              assumptions the data is built from
scripts/generate_*.py          one generator per pillar
scripts/push_to_sheets.py      pushes generated data into Google Sheets
dashboard/                     one module per dashboard tab
app.py                         entry point
```

## Running it locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/generate_data.py
streamlit run app.py
```

Connecting to your own Google Sheet (instead of the one this project ships
against) requires a Google Cloud service account — see
[SETUP.md](SETUP.md) for the full walkthrough.

## About this project

Built by [Tatiana Reyes Jové](mailto:tl.reyes.jove@gmail.com) as a hands-on
way to learn Python, data pipelines, and building/deploying a real web app —
modeled loosely on a real-world solar lighting company, but with entirely
invented data, numbers, and business details.
