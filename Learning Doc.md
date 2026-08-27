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

### 2.4 — Wiring the real budget into Finance, and two more findings

Closed out the loose thread from 2.1: `budget_revenue`/`budget_ebit` in
the Finance tab were still the old noise-around-actual placeholder. Fixed
properly, in two parts:

1. **Budget columns now read straight from the financial model's monthly
   P&L** (Revenue and EBIT rows on `USA PL` / `Nigeria PL`), not a random
   variance formula.
2. **Actual Opex is now built from the same cost structure as the
   budget** — real headcount totals, the same fixed categories (rent,
   travel, etc. spread flat monthly), the same commission-on-revenue
   logic — instead of the old flat "32% of revenue" guess. This matters
   for the same reason the Sales/Finance reconciliation in 1.3 mattered:
   if Actual and Budget are built from two unrelated cost models, any
   "variance" between them is meaningless noise, not a real business
   signal.

**Finding #1 — the margin assumption didn't match reality.** After
wiring this up, actual EBIT was coming in wildly ahead of budget (~190%
in one check). Investigating why: the model's 44.5% blended margin
assumption was a *theoretical* average (based on each product's average
deal size), but the actual generated deals — with a fixed random seed
and a relatively small sample (~100 Closed Won deals total) — happened to
draw more high-margin Sol 4/5 deals than that average predicts (Sol 5
alone realized ~40% of revenue in the data, versus ~35% theoretically
expected). Recalibrated the model's margin assumption to 47.3% — what
the actual generator really produces, not a theoretical estimate — which
narrowed the gap substantially. The residual gap is real and expected:
2025 and 2026 each independently realize a slightly different margin
purely from small-sample randomness (46.2% vs. 48.7%), and no single
blended assumption can perfectly match two different real outcomes at
once. That's normal — real budgets don't perfectly predict actuals either.

**Finding #2 — EBIT needs a different comparison than Revenue.** Even
after the margin fix, 2026 YTD EBIT still looked like it was beating
budget by ~50%, which felt too large to just accept. You caught the real
issue: EBIT was being compared against a *prorated* slice of the annual
budget (Jan-Aug's budgeted EBIT specifically), the same technique used
for Revenue. But that double-counts the model's seasonality assumption —
fixed costs (most of Opex) don't scale down in slow months the way
revenue does, so a straight 8/12 slice of annual EBIT understates what a
real company would expect to have banked by August. The fix:
`config.read_annual_budget()` now pulls the FULL year's budgeted EBIT
(the "Annual" column, not a sum of already-happened months), and YTD
actual EBIT is compared against that instead. Same $1.84M actual EBIT,
now correctly read as **75% of the full year's plan** (against 67% of
the year having elapsed) — a believable, modestly-ahead-of-pace result,
not an alarming overshoot. The lesson generalizes: Revenue is fine to
prorate for a YTD comparison because it's expected to accrue roughly
with time; a metric with a large fixed-cost component (EBIT, margin)
usually isn't, and should be checked against the full-period target
instead.

### 2.5 — Explicit quarterly revenue targets (2026 only)

You wanted a real quarterly pacing target — 10%/20%/30%/40% for 2026 —
distinct from what the monthly seasonality curve already implied per
quarter (~22/24/24/31). Worth naming the distinction we talked through:
the *implied* quarterly totals were never a deliberate decision, just
whatever fell out of summing three months of the existing curve. What
you asked for is a genuine planning input — a number Finance would have
picked on purpose — so it needed its own place in the Assumptions tab,
not just an after-the-fact grouping of monthly numbers.

Your call: the new quarterly targets *replace* the monthly breakdown for
2026 (not sit alongside it as a second, possibly-disagreeing number —
that would've reintroduced the exact "two things both claim to be true"
problem fixed a few times already). 2025 stays on the seasonality curve
alone, since it's complete and settled — this is a forward-looking tool
for the year still in progress.

Mechanically: 2026 monthly revenue is now `annual target × that
quarter's target % × (this month's seasonality weight ÷ the sum of
weights within its own quarter)` — same relative shape month-to-month
within a quarter as before, but each quarter now ties to its explicit
target exactly (confirmed: 10.0/20.0/30.0/40.0%, annual total unchanged
at $15M — the quarterly %s summing to 100% is what guarantees that).

Data-layer only for now, by request — this doesn't show up on the
dashboard yet.

---

## Phase 3: The Streamlit App

### 3.1 — Building the app

Three tabs (Sales / Finance / Inventory, your call over a single scrolling
page), styled with the brand guide's actual colors and Inter typeface.
Structure:

- `app.py` — entry point: page config, header, the Refresh button, tabs.
- `dashboard/data.py` — the only place that talks to Google Sheets.
  Two different caches, deliberately separate: the connection itself
  (`st.cache_resource`, never expires — expensive to set up, safe to
  reuse) versus the actual data (`st.cache_data`, cleared by the Refresh
  button). Without that split, "Refresh" would have no way to know the
  difference between "reconnect" and "re-pull the numbers."
- `dashboard/styling.py` — every color pulled from `Lumin Light Brand
  Guide.html`, not invented here. Two small palette decisions worth
  noting: Sol 1-5 use a single blue ramp (light to dark, ending at Navy
  Primary itself for Sol 5) since they're a real ordinal tier sequence —
  but the four buyer types get four genuinely distinct hues instead,
  since there's no inherent order among Government/Distributor/NGO/
  Multilateral. Status colors (green/amber/red) stay reserved for
  Inventory alerts only, per the brand guide's explicit rule.
- `dashboard/sales.py`, `finance.py`, `inventory.py` — one module per
  pillar.

**"Today" is the data's own snapshot date, not your computer's clock.**
`app.py` reads it from Inventory's `as_of_date` column rather than calling
the real system date. This data was generated once, as of a specific day
— if the app used the live clock instead, "deals closing this quarter"
and similar time-relative metrics would silently drift out of sync with
what the data actually reflects the moment this is opened on a different
day (which, for a deployed dashboard, could be months later).

**The "target" numbers don't live in this project's Python code.** Sales'
"% of annual target" is calculated by summing Finance's `budget_revenue`
column — not by importing `scripts/config.py` or reading the financial
model directly. That's a deliberate architecture choice, not laziness:
the whole point of the Google Sheet is that it's the *only* thing the
dashboard reads from, mirroring how a real deployed version would have no
access to the source systems (QBO, the CRM, the financial model) at all —
only to what those systems already pushed into the Sheet.

### 3.2 — A real gap found while testing against the live Sheet

Building the Finance tab's "EBIT vs. full-year budget" metric (see 2.4)
surfaced a genuine data-model problem, not just a dashboard bug: the
Finance tab only had rows through today, so there was literally no way to
read "the full year's budget" without the dashboard reaching outside the
Sheet — which would have broken the "dashboard only reads the Sheet"
architecture we'd just agreed was the correct real-world pattern.

The fix belonged in the data itself, not the dashboard: `generate_finance.py`
now creates rows for the WHOLE fiscal year, immediately. Budget columns
are populated for all 12 months from day one — exactly how a real annual
budget actually works, existing in full before any of the year's actuals
happen. Actual columns (`revenue`, `cogs`, `opex`, `ebit`, `cash_balance`)
stay blank for months that haven't happened yet — genuinely unknown, not
zero. Getting this distinction right mattered downstream too: an early
version of the "Actual vs. Budget" chart showed the Actual line crashing
to zero after August instead of just stopping, because pandas'
`.groupby().sum()` treats an all-blank group as 0 by default — fixed with
`min_count=1`, which keeps a genuinely-unknown group as blank instead.

### 3.3 — A real bug: the pipeline-aware reorder alert was silently broken

While building the Inventory tab's alert logic (see the module's own
docstring for the full formula), the "Warning" tier consistently showed
zero — a red flag, since a portfolio of realistic products/deals should
turn up at least a few borderline cases by chance. Manually recomputing
one row by hand in a Python shell caught it: the code wrote
`open_deals.product == product`, using **attribute access** to reach the
"product" column. But pandas DataFrames have a *built-in method* called
`.product()` (computes a product of values) — attribute access finds that
method first and silently shadows the column of the same name. The
comparison was quietly evaluating "is this bound method object equal to
this string," which is always `False` — so the pipeline filter matched
nothing, ever, for any product, and the whole pipeline-aware calculation
had been computing zero demand for every single row without raising an
error anywhere. Fixed by switching to bracket notation
(`open_deals["product"]`), which always means "the column," never a
method. **General lesson worth keeping:** in pandas, bracket notation
(`df["column"]`) is the safe default for column access; attribute access
(`df.column`) is a convenience that quietly breaks for any column whose
name collides with a real DataFrame method or attribute (`product`,
`count`, `sum`, `min`, `max`, `T`, `mode`, and others) — and the failure
mode isn't a crash, it's a wrong answer that looks like a legitimate
result.

Fixing that bug changed the actual demo data in a good way: instead of 0
Warning-tier rows, a rerun turned up 3 Critical / 3 Warning / 4 Healthy —
including Sol 1 in Houston, whose stock (44,806 units) sits comfortably
above its static reorder point (32,600) and would look completely fine on
a naive check, but drops to a Warning once near-term pipeline demand is
factored in. That's the exact scenario the spec describes as the reason
this metric exists.

One more refinement made alongside the bug fix: the pipeline calculation
originally summed *every* open deal for a product, regardless of how far
out its expected close date was. That over-counts risk — a deal that
won't close for 8 months shouldn't trigger an urgent reorder flag today,
since there's plenty of time for a normal restock before it could
possibly close. Now only deals expected to close within
`REORDER_LOOKAHEAD_MONTHS` (1 month — matching `AVG_LEAD_TIME_MONTHS`,
the same lead-time assumption `reorder_point` itself is built on) count
toward the alert.

### 3.4 — Channel revenue targets, and a genuinely tricky rendering bug

You wanted each Channel (Institutional/Commercial) to have its own
target, with progress shown against it — same idea as the quarterly
targets in 2.5, applied to a different cut of revenue. Same principle
applied again: a target needs to be a real planning input someone
actually chose, not something invented on the fly. So the % splits
(USA 55% Institutional / 45% Commercial, Nigeria 50/50) were picked by
looking at where each subsidiary's *actual* 2026 channel mix already
sits (USA running ~56/44, Nigeria ~49/51) — a believable near-term goal
instead of an arbitrary number that would've made the resulting gauges
either trivially "done" or absurdly far off on day one.

Mechanically this followed the exact same pattern as the quarterly
target: a new "Channel Revenue Target Split" section on the Assumptions
tab (appended after the existing Starting Cash Balance section, not
inserted earlier — inserting rows would've shifted every fixed cell
reference `config.py` already depends on, like `C15` for the benefits
loading %). `config.read_channel_targets()` reads those percentages and
multiplies them against each subsidiary's existing annual revenue
target, so the dollar figures are never a second copy of a number that
lives elsewhere. From there it flows exactly like `budget_revenue`
already does: `generate_finance.py` spreads the annual target flat
across 12 months into two new Finance-tab columns
(`budget_institutional_revenue`, `budget_commercial_revenue`, 2026 only
— matching the quarterly target's "this year only" scope), and the
dashboard sums that column back over the year to get the annual figure,
same "sum the monthly column" trick used everywhere else on this tab.

The chart itself — a semicircular gauge per channel, prototyped first in
a disposable test app before touching the real dashboard — worked on the
first real attempt (Vega-Lite arc marks stack into a half-circle by
setting `theta`'s scale range to `[-π/2, π/2]` instead of the usual full
circle, the same mechanics as a donut chart just rotated into a dome).
The hard part came after: switching the entity selector between
Consolidated/USA/Nigeria intermittently left one or both gauges
completely blank — no error banner, nothing in the UI, just an empty
arc. Chasing it down: the browser console showed a recurring
"Unrecognized data set" error from Vega-Embed on every entity switch,
and inspecting a blank gauge's actual SVG showed the mark *groups*
existed (Vega had built the scene graph) but were empty — no `<path>`,
no `<text>`. That's consistent with Streamlit trying to *patch* an
existing chart's live Vega view in place across a rerun (swap in new
data by name) rather than fully rebuilding it, and the patch silently
failing to find the dataset it expected.

The fix was changing how the gauge's Altair spec was put together, not
the data itself: the first version layered three *separate*
`alt.Chart(...)` objects (the arc, the big percentage text, the small
title text), each built from its own tiny one-off DataFrame — three
distinct datasets in one layered spec. Every other multi-layer chart on
this tab (the bullet charts, the channel pie) instead builds every layer
off *one* shared `base = alt.Chart(df)`, filtering down to one row for
text layers with `transform_filter` where needed (the same technique
`bullet_chart`'s inside/outside actual-value labels already used).
Rebuilding the gauge the same way — one shared dataset, `transform_filter`
for the text — made the blanking disappear completely across repeated
entity switches, including rapid back-to-back clicks. Never fully
confirmed *why* three-datasets-in-one-spec specifically breaks
Streamlit's patch path and one-dataset doesn't (that's Streamlit/
vega-embed internals, not something worth chasing further for this
project) — but the fix is consistent with every other layered chart in
this codebase already following the "one shared base dataset" pattern,
which in hindsight was already the established convention here for a
reason.

### 3.5 — Rebuilding Finance: Recognized Revenue, and a real modeling bug

Tatiana asked for a full redo of the Finance tab — a Financial Performance
chart grid, a Cash & Risk KPI section, and an AR Aging Detail table,
matching the exact shape of the Sales tab's own three sections. Most of
the new charts turned out to already be one small step away from existing
data: Gross Margin by Product Tier was already being computed (Sol 1-5
margins already ramp ~35% -> 55%, the real premium/low-volume vs.
low-cost/high-volume story Tatiana wanted, because `config.PRODUCTS`
already modeled it that way); Cash Balance was already tracked monthly,
just needed a trailing-12-month line chart instead of the old all-history
area chart; EBITDA is just EBIT + D&A, and D&A was already being computed
internally — it just needed to be exposed as its own column
(`generate_finance.py`) instead of staying a local variable. Opex vs.
Budget needed one real addition: a `budget_opex` column, built with the
exact same cost-structure formula `generate_finance.py` already uses for
actual opex, just fed `budget_revenue` instead of actual revenue for the
commission term, and with no execution-variance noise (a plan doesn't
have "noise" — that's what makes something an actual, not a budget).

The one genuinely new concept — and the one that caused a real bug —
was **Recognized Revenue**. Tatiana was specific: it needed to be a real,
separate, LOWER number than Sales' "Booked YTD," because not every
booked deal has been delivered and invoiced yet. That meant building
actual invoice-level data for the first time: a new `generate_ar.py`,
one invoice per Closed Won deal, with an issue date (a short lag after
the deal closes — delivery/invoicing takes real time), a due date
(net-30), and a payment date drawn from a distribution that's slower for
Institutional buyers than Commercial — the same "institutional buyers
pay slowly" story `config.AR_LAG_DAYS` already told elsewhere in this
project, just finally given real teeth via invoice-level data instead of
staying a comment. That same AR data is also what makes DSO and AR
Overdue $ possible, and it's the direct source for the AR Aging Detail
table.

The first version defined "Recognized Revenue YTD" as: sum up every
invoice whose ISSUE DATE falls in 2026. That seemed reasonable, but
verifying it against Booked YTD (compute both, compare) caught a real
problem — Recognized Revenue came out **higher** than Booked YTD, the
opposite of what was asked for. The cause: this business's seasonality
curve weights November and December the heaviest (year-end institutional
budget flush), so a meaningful chunk of *2025's* December bookings get
invoiced a few weeks into *2026* — dollars that were never part of 2026's
bookings in the first place, inflating 2026's "recognized" total past
2026's own booked total. Any fixed invoicing lag will always have this
same boundary effect at a year change; the fix wasn't a bigger or smaller
lag, it was scoping by the wrong thing. The corrected version scopes
Recognized Revenue to the SAME cohort of deals as Booked YTD (deals whose
actual_close_date falls in the year in question), and only counts the
portion of that cohort already invoiced as of today (`issue_date <=
as_of`). That makes Recognized Revenue a guaranteed subset of Booked —
always less than or equal, never more — which is what "not every booked
deal has been invoiced yet" actually means. **General lesson worth
keeping:** whenever a new number is supposed to relate to an existing one
in a specific way ("always lower," "always a subset of"), verify that
relationship holds on real generated data before trusting the chart —
the code can run cleanly and still produce a number that's directionally
backwards.
