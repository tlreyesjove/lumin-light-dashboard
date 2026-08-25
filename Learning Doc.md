# Lumin Light Dashboard — Learning Doc

A running log of what got built, in what order, and *why* — not just what the
code does, but the reasoning behind each decision. The goal: you should be
able to read any section here and then explain that part of the project
without looking at the code.

Updated stage by stage as we go. If something here stops matching the code
(we changed our minds later), say so and I'll fix this doc, not just the code.

---

## Phase 1: Synthetic Data Generation

### 1.1 — Setup and scope

Read `Lumin Light Project Spec.md` and `Lumin Light Brand Guide.html` to
understand the project. Two decisions made before writing any code:

- **Used the spec's default assumptions as-is** — revenue split ($9M USA /
  $6M Nigeria), warehouse cities (Houston, Lagos), deal size ranges per
  product tier. Nothing overridden at the start.
- **Chose to have Python write directly into Google Sheets** (via the
  Sheets API), rather than generating CSVs for manual copy-paste. This
  mirrors the real architecture described in the spec — in a live version
  of this project, Zapier would poll a real system and write rows into a
  Sheet on a schedule. Our Python script plays Zapier's role for now.

Set up git in the project folder, with a `.gitignore` covering: the Python
virtual environment, generated CSVs (regenerable, not the source of truth),
and anything Google-credential-related (`.env`, `credentials/*.json`) —
those are specific to your Google account and should never be committed,
especially since this repo is meant to go public eventually.

### 1.2 — Building the three data generators

One Python script per dashboard pillar, all driven by a single
`scripts/config.py` file holding every assumption (revenue targets, product
pricing, deal size ranges, warehouse locations, etc.) — the idea being: if
a number ever looks wrong, there's exactly one file to open, not a hunt
through multiple scripts.

**Sales (`generate_sales.py`)** — one row per deal.
- The spec gives *dollar* ranges per product tier, not unit prices. Unit
  prices were invented (a judgment call, flagged for review) so a unit
  quantity could be worked backwards from each deal's dollar value — that
  quantity is what lets Inventory demand later be calculated from real
  Sales activity.
- Each deal gets a buyer type (Government / Distributor / NGO /
  Multilateral) and a fictional buyer name — real country names are used
  for Government buyers (plausible and low-risk), but Distributor/NGO/
  Multilateral names are invented rather than using real organizations
  like UNHCR or UNICEF, to keep the data unambiguously fictional.
- Win rate and typical sales-cycle length vary by buyer type (e.g.
  government tenders take longer and are harder to win than a repeat
  distributor order) — small touches that make the dataset feel like a
  real business rather than uniform random noise.

**Finance (`generate_finance.py`)** — one row per (month, subsidiary).
- Originally: revenue was sampled independently, *targeting* the same
  annual figures as Sales, but not actually built from Sales data. This
  got fixed later (see 1.3).
- Cash balance models a real working-capital effect: institutional buyers
  are slow payers, so cash *collected* in a given month is modeled as the
  *previous* month's revenue, while costs are paid the same month they're
  incurred. That lag is what produces believable down months in cash even
  when the business is profitable, instead of cash just tracking revenue
  in lockstep.

**Inventory (`generate_inventory.py`)** — one row per (product, warehouse).
- Stock levels are deliberately randomized so most rows look healthy but a
  few sit below or near the reorder point — a dashboard where every metric
  is always fine isn't a useful demo of a reorder-alert feature.
- This script does **not** compute the "pipeline-aware" reorder alert the
  spec calls for (flagging low stock because a big near-certain deal is
  about to close, even if today's stock looks adequate). That logic needs
  both the Inventory tab and the Sales tab's open pipeline together, so it
  belongs in the Streamlit app (Phase 3), not in data generation.

### 1.3 — Fixing Sales/Finance reconciliation

**The problem, caught by you:** Sales' Closed-Won total and Finance's
revenue total were two independently-generated numbers that happened to
land in the same ballpark — not actually connected. When checked, they
were off by roughly $1M with no real explanation for the gap other than
coincidence.

**The fix:** Finance's `revenue` and `cogs` columns are now *calculated
from* the Sales tab — grouped by month and subsidiary, summing up the
actual Closed Won deals that closed in each one. They're not two numbers
that happen to agree; they're the same underlying data, viewed two ways.
`scripts/generate_data.py` runs an explicit reconciliation check every time
data is generated — it will hard-fail (an `assert`) if the totals ever
drift apart again.

Side effect of this fix: deal generation switched from "generate a fixed
*count* of deals" to "keep generating deals until Closed-Won value hits
the period's *target*." The fixed-count approach was too noisy — a few
large deals (some worth up to $1M) landing in one 12-month period by luck
could swing that period's total by 20%+, which at one point flipped
year-over-year revenue growth negative by pure chance.

### 1.4 — Inventory reorder point: real formulas

You supplied the actual supply-chain formulas to use:

```
Safety Stock  = (Max Monthly Demand x Max Lead Time)
                - (Avg Monthly Demand x Avg Lead Time)
Reorder Point = (Avg Monthly Demand x Avg Lead Time) + Safety Stock
```

With lead time assumed at 1 month (both average and worst case, per your
call, for a ~100,000-unit replenishment order), the two formulas simplify
algebraically to **Reorder Point = Max Monthly Demand** — i.e., "always
hold enough stock to cover the single busiest month you've actually seen."
The formula is still written out in full in the code (not hardcoded to
that shortcut), so it'll keep working correctly if average and max lead
time are ever set to different values (e.g. if Nigeria's warehouse gets a
longer/less reliable lead time than Houston's later).

Average and max monthly demand are pulled from the *actual* Closed Won
deals in `sales.csv` (grouped by month), the same reconciliation principle
as the Finance fix — Inventory's idea of demand is traceable back to real
generated Sales activity, not a separate estimate.

### 1.5 — Splitting Stage from Status

You wanted `stage` and `status` to be genuinely separate, non-overlapping
fields (matching how real CRMs like Pipedrive model this):

- **`status`** — Open / Won / Lost. The simple, always-populated field.
- **`stage`** — Prospecting (10%), Qualification (10%), Proposal (50%),
  Negotiation (90%). Only applies to **Open** deals; blank for anything
  Won or Lost, since that information now lives in `status` instead.

The percentage next to each stage is its win probability, which is what
`weighted_value` (deal_value × probability) is built from — this is the
number a "pipeline weighted value" KPI on the dashboard will sum, filtered
to `status == "Open"`.

---

## Phase 2: Connecting to Google Sheets

Walked through the one-time Google account setup together (all done by
you, since account creation isn't something Claude Code does on your
behalf):

1. Created a Google Sheet ("Lumin Light Data")
2. Created a Google Cloud project ("Lumin Light Dashboard")
3. Enabled the Google Sheets API on that project
4. Created a service account (`lumin-light-sheets-writer`) — a "robot
   login" with no human behind it, used only so a script can be granted
   access to edit one specific Sheet
5. Downloaded its JSON key file, saved locally as `credentials/service_account.json`
   (gitignored — this file is effectively a password and should never be
   shared or committed)
6. Shared the Sheet with the service account's email as an **Editor**
7. Filled in `.env` with the Sheet's ID

Ran `scripts/push_to_sheets.py`, which reads the three CSVs out of `/data`
and writes each one into its own tab (Sales, Finance, Inventory) in the
Sheet — overwriting whatever was there before. **Result: 518 Sales rows,
48 Finance rows, 10 Inventory rows, successfully written.**

This closes the loop the spec describes: synthetic data plays the role a
real Zapier automation would play, landing in a Sheet that a dashboard can
read from — without the dashboard itself needing to know or care that the
data behind it is fake.

**A conceptual detour worth remembering:** we talked through why "Zapier
saves to Google Drive" (as it does in the real Be Girl setup) and "Zapier
writes rows into a Google Sheet" (what we built here) usually mean the
same underlying pattern — a Sheet *is* a file that lives in Drive, and a
live spreadsheet in a Shared Drive folder is functionally identical to
what we've built, just organized under a team folder instead of a
personal one. The alternative (Zapier dropping a raw CSV/Excel file into a
Drive folder with no live spreadsheet) is a real pattern too, but it's
typically used for archival/backup, not for feeding a live dashboard,
since something still has to open and parse that file before it's usable.

---

## Phase 3: The Streamlit App

*Not started yet.*
