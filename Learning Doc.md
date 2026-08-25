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

### 2.1 — Switching to a real Jan-Dec fiscal year

You caught a real gap while poking around the Finance tab: there was no
genuine, independently-set revenue *target* living anywhere in the data —
the $15M figure only existed in `config.py`, invisible to the dashboard,
and the existing `budget_revenue` column was secretly derived from actual
revenue (plus noise), so it could never show a meaningful "did we hit
target" story — it would always land close to 100% by construction.

Before fixing that, you asked a clarifying question that turned into a
bigger change: the dashboard's "current year" was actually a rolling
Sep-Aug window (the spec's original trailing-12-months default), not a
real Jan-Dec fiscal year. Once we agreed Lumin Light's fiscal year is the
calendar year, "2026 YTD" only had 8 months of data (Jan-Aug) sitting
under a $15M *annual* target — looking artificially behind, since it was
being compared to a full year's goal.

**What changed in `config.py`:** `CURRENT_PERIOD` is now fiscal 2026
(Jan 1 - Dec 31, though real data only ever exists through TODAY, since
future months haven't happened). `PRIOR_PERIOD` is now a full, clean
calendar year 2025. **2024 was dropped entirely** — it only ever had 4
months of coverage (Sep-Dec), so it couldn't stand as a real comparison
year, and extending it further back wasn't worth the added complexity for
what this dashboard needs.

That single change had ripple effects worth understanding, since they're
the kind of thing that's easy to get subtly wrong:

- **Sales**: deal generation for the current period now targets a
  *prorated* share of the annual target (target × fraction of the fiscal
  year elapsed — about 65% as of today), not the full annual figure.
  Otherwise 8 months of closed deals would need to already equal a full
  year's worth of business, which would look like the company was way
  ahead of pace rather than on a normal trajectory.
- **Finance**: revenue growth vs. prior period now compares YTD to
  *the same YTD months* last year (Jan-Aug 2026 vs. Jan-Aug 2025), not 8
  months of this year against a full 12 months of last year — comparing
  different-length periods would have made growth look artificially bad
  regardless of how the business is actually doing.
- **Inventory**: this was the subtlest one. Demand stats initially switched
  to "fiscal YTD only" along with everything else — but early in a fiscal
  year, that's a small sample, and one slower-moving product/warehouse
  combo (Sol 3, Nigeria) came back with **zero** demand and a **zero**
  reorder point, purely because no Sol 3 deals happened to close in those
  particular 8 months — not because real demand was zero. Fixed by
  switching Inventory's demand window to a **trailing 12 months ending
  today**, independent of the fiscal year boundary. This is also just
  more realistic: a warehouse's restocking cadence doesn't reset itself
  every January 1st.

Current numbers after the change: USA YTD revenue is $6.03M (103% of a
prorated $5.84M YTD target, +8.9% YoY); Nigeria YTD is $3.97M (102% of a
prorated $3.89M YTD target, -3.9% YoY) — a believable mixed picture, not
everything trending the same direction.

**Superseded by 2.2 below:** the plan to fix `budget_revenue`/`budget_ebit`
with a flat monthly split turned into something bigger — a real financial
model, described next.

### 2.2 — Building a real 2025-2026 financial model

You pointed out the actual real-world gap: in a live version of this
project, Finance would build and approve a budget *before* the year
starts — a real financial model, not a formula guessing at "revenue plus
some noise." You offered your real Be Girl financial model as a
structural template to build Lumin Light's version from.

**Handling the real template safely.** The project's hard rule is that no
real Be Girl data can ever end up in this repo, which is meant to go
public. Before touching the file: gitignored it immediately
(`Be Girl*.xlsx`) so it could never accidentally get committed, confirmed
it was still untracked, then only read its *structure* — tab names, the
Revenue → COGS → Gross Profit → Opex → EBITDA → EBIT flow, how Cash Flow
rolls forward month to month. One tab (Salaries) had real named
employees and real compensation — that entire concept (a named roster)
was rebuilt from scratch with invented generic role titles and invented
numbers, nothing carried over. You said you'd delete the real template
from this folder once the Lumin Light version existed.

**Scope decisions, made together before building anything:**
- 2025's budget set close to (not identical to) what Sales actually
  achieved that year — see 2.3 below for how this ended up becoming an
  exact match instead.
- Opex kept to 7 top-level categories (Salaries & Benefits, Sales
  Commission, Rent, Travel, Professional Services, Marketing, Freight &
  Logistics, G&A/Admin) rather than the template's much deeper
  sub-category breakdown — matches a 20-person company's actual
  complexity.
- A real ~20-role headcount roster (generic titles, invented comp) drives
  the Salaries line bottom-up, rather than a single flat number.
- The P&L stops at EBIT — no interest/tax/net income below it, since
  that's all the dashboard actually needs.
- Skipped rebuilding the template's unit-level "Sales Forecast" tabs
  (where a real sales team would input their own unit-by-unit
  projections) — Lumin Light's *actual* side already has that unit
  detail in the Sales tab; the model only needs to produce monthly $
  figures for the dashboard to compare against.

**A margin mistake caught by asking "wouldn't gross margin just be
revenue minus COGS?"** First pass used 39.6% — the *average of the five
products' margin percentages*. That's wrong: it treats Sol 5 (rare, but
up to $1M a deal) as equally important as Sol 1 (common, ~$8/unit) just
because they're each "one of five products." The correct blended margin
weights by *revenue*, not by product count — mathematically identical to
(Total Revenue − Total COGS) / Total Revenue, which is the actual
definition. That works out to 44.5%, which also matches what the real
generated Sales data shows (46-49% realized) far better than 39.6% did.

**The result:** a 6-tab workbook (Assumptions, Headcount, USA PL, Nigeria
PL, Consolidated PL, Cash Flow) — every number an editable input on the
Assumptions or Headcount tab, everything else a formula. No intercompany
elimination line (unlike the real Be Girl model, where Mozambique buys
from the US entity at a markup) — Lumin's two subsidiaries both buy
directly from an external supplier at the same price, so Consolidated is
a straight sum of the two subsidiary P&Ls. 2025 budget: $12.95M revenue,
10.0% EBIT margin. 2026 budget: $15.0M revenue, 13.4% EBIT margin — the
margin *expansion* wasn't forced; it falls out naturally because most
Opex is fixed/headcount-driven while revenue grows ~16%.

One real finding from the build: USA and Nigeria have very different
margin profiles standalone — USA's 2025 EBIT margin is a thin 3.3%
(13 of the 20 roles, and the priciest ones, sit in USA) versus Nigeria's
20.2%. Not a mistake — a believable "HQ absorbs the overhead" story — but
worth knowing before someone looks at the dashboard and asks about it.

**Verifying the formulas actually work.** openpyxl writes formulas as
text with no computed values — nothing is "real" until something
actually executes them. Checking that required LibreOffice (a free
Excel-equivalent that can run headless and force a full recalculation),
which wasn't installed. You installed it yourself by downloading straight
from libreoffice.org rather than going through Homebrew — simpler, no
terminal work needed. Recalculating then confirmed all 1,874 formulas in
the workbook evaluate with zero errors, and the computed totals matched
hand-calculated expectations exactly.

### 2.3 — Making the financial model the actual source of truth

You asked whether 2025's Sales actuals could be made to match the
financial model exactly, with the model as the authority — not just
"close," which is what 2.2 originally produced (+3.3% actual over
budget). Two changes:

1. **`config.py` no longer hardcodes revenue targets.** It now opens the
   financial model workbook at import time and reads the 2025 and 2026
   figures straight from its Assumptions tab. If the model's numbers
   ever change, regenerating data picks up the new targets automatically
   — nothing to keep in sync by hand, the exact failure mode already
   fixed once for Sales/Finance (see 1.3) and avoided here from the start.
2. **2025's Closed Won deals get rescaled to hit the target exactly**
   (not just "at least" the target, which is what generates the natural
   overshoot for 2026). This only happens for the *prior* period — 2025
   is complete and settled, so its actual revenue should tie to the
   approved budget precisely. 2026 deliberately keeps its natural
   variance, since the year is still unfolding and a real "are we on
   pace" comparison needs room to move.

Confirmed after rerunning the generators: 2025 Sales actual revenue now
equals the financial model's 2025 budget to the penny, for both
subsidiaries. Finance and Inventory, which both derive from Sales,
regenerated cleanly on top of that with no other changes needed.

---

## Phase 3: The Streamlit App

*Not started yet.*
