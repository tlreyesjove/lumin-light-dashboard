# Lumin Light — Leadership Dashboard: Project Spec

## What this is

A leadership dashboard for a fictional B2B company with a team of 30 people, built as a personal learning and portfolio project — not a Be Girl deliverable. This dashboard would be for their senior leaders to use daily, as a single source of truth to check in on key KPIs and the overall health of the company. It's modeled on a real company (bright-products.com, solar lamps for humanitarian aid) and informed by everything learned advising Be Girl on its own data/dashboard needs, but it uses **entirely synthetic, made-up data**. No connection to any real company's systems, accounts, or data.

**Why it exists:** to build real skills — Python, data pipelines, a working web app, deployed and public on GitHub and visualized on Streamlit — as a genuine, defensible portfolio piece. Separate and distinct from the real Be Girl advisory work happening in parallel.

**Hard boundary:** this project must never contain real Be Girl data, documents, or references. It lives in its own project folder, entirely separate from the Be Girl Dashboard Project folder, because this repo is intended to go public on GitHub eventually.

## How we work together on this

This is a learning project, not a "build it for me" task — the point is that Tatiana comes out the other side able to explain and defend every part of it. That means:

- **This is vibe coding, done as a real partnership — not delegation.** Tatiana isn't a programmer, so Claude Code writes the code. But this still counts as "coding with AI" (one of the six AI-native skills from the roadmap) as long as Tatiana stays actively engaged rather than passively accepting output: reading what Claude Code produces, asking it to explain non-obvious pieces, testing behavior, and questioning anything that looks off.
- **The bar: can Tatiana explain and debug what gets built.** That's the actual test — and it's also the interview test ("walk me through something you built"). Practically: whenever Claude Code builds something with real logic in it (the reorder-alert calculation, the Sheets connection, anything non-trivial), it should explain the piece back to Tatiana in plain English before moving on. Cheap to do, and it's what turns "I directed a build" into "I can explain how this works."
- Tatiana drives scope, design, and data decisions throughout — Claude Code should propose and explain options, not just execute silently.
- **Tatiana handles all account creation and external setup herself.** GitHub account/repo, Streamlit Community Cloud, Google account/Sheets, Zapier/Make (if used) — Claude Code should walk her through each step (what to click, what to name things, what to paste where) but should not attempt to sign up for or log into these on her behalf.

## The company

**Lumin Light** — sells portable solar lighting products to institutional buyers (governments, NGOs, multilateral agencies, distributors) via tender and direct sales, for humanitarian aid, disaster response, and off-grid communities. Pure B2B — no direct-to-consumer.

One company, two subsidiaries (mirrors real-world multi-entity complexity — a parent with a regional leg):
- Parent: **Lumin Light USA** (HQ)
- Regional subsidiary: **Lumin Light Nigeria**

### Products — the Sol line

Five tiers, each with different pricing, margin, and expected order volume (higher tier = higher price/margin, lower volume):

| Product | Positioning |
|---|---|
| Sol 1 | Pocket-sized, lowest cost, highest volume — personal preparedness |
| Sol 2 | Basic off-grid household lighting, affordable |
| Sol 3 | Portable, with integrated phone charging |
| Sol 4 | Modular, built for large-scale emergency deployment |
| Sol 5 | High-efficiency, extended runtime — shelters and facilities (premium, lowest volume) |

### Buyer types (4)

- Government
- Distributor
- NGO
- Multilaterals (UN agencies and similar — e.g., UNHCR/UNICEF-equivalent)

## Dashboard scope — three pillars

### Sales
- Pipeline weighted value by stage, and as a % of target
- Total deals won year-to-date, and as a % of target
- Deals closing this quarter
- Win rate — total, and by buyer type

### Finance
- Revenue — total, and by subsidiary
- Revenue growth (vs. prior period)
- Margin by product (Sol 1 vs. Sol 5 should show meaningfully different unit economics)
- EBIT
- Cash position and burn rate
- Budget vs. actual — org-level total only (Lumin Light sells products, not grant-funded projects, so the per-project granularity that mattered for Be Girl's real budget concern doesn't apply here)

### Inventory
- Stock on hand, by product and by warehouse location
- Reorder alerts below threshold — **factoring in weighted pipeline demand**, not just static reorder points (e.g., a large near-certain deal about to close should be able to push a "reorder" flag even if current stock looks adequate on its own). This is the one metric that deliberately connects the sales and inventory pillars rather than treating them as isolated views.

## Data approach

All data will need to be created, then loaded into Google Sheets, rather than pulled from any live source — but the pipeline is architected the way a real client project would actually be built, so the practice transfers.

**How a real version of this would work:** Lumin Light's real underlying systems (QuickBooks Online for finance, a CRM like Pipedrive for sales, an inventory tool for stock) generally don't expose data in a form a dashboard can read directly, and building bespoke API/OAuth integrations for each one is expensive and fragile. The standard lightweight pattern is: **Zapier or Make polls each source system on a schedule and writes the results into a Google Sheet**, which acts as a simple, transparent staging layer — easy for a non-technical client to inspect or fix by hand if something looks wrong, and one consistent format for the dashboard to read from, regardless of how many different source systems feed into it.

**How this demo mirrors that:** since there are no real QBO/CRM accounts to connect, the synthetic data plays the role that Zapier's output would — it lives in a Google Sheet (one per pillar, or one sheet with three tabs), just as if a real Zapier automation had written it there. The dashboard reads from those Sheets, not from hardcoded data baked into the app. The result is a codebase that already speaks the right architecture: swap the "synthetic data → Google Sheet" step for "real Zapier automation → Google Sheet" later, and the dashboard itself doesn't need to change.

**Refresh behavior:** the dashboard is not meant to poll continuously in the background — that's unnecessary complexity for data that only changes daily at most. Instead:
- Data loads fresh from the Google Sheet each time the dashboard is opened
- A **manual "Refresh" button** on the dashboard re-pulls from the Sheet on demand, so the user isn't stuck looking at stale numbers between page loads without having to reload the whole app

*On Tatiana's question — can the Refresh button actually trigger Zapier to re-pull, not just re-read the Sheet?* Yes, technically: Zapier supports a "Webhook" trigger, so the Streamlit button could send a request that kicks off the Zap on demand, rather than waiting for its next scheduled run. Two honest caveats: (1) there'd be a short lag between hitting the button and the Sheet actually updating, since the Zap still has to run — the button couldn't show the new data instantly; (2) in this demo there's no real source system for a Zap to pull from, so there's nothing to actually wire this up to yet. **Recommendation: treat this as a v2/stretch feature, not part of the v1 build.** V1's refresh button just re-reads the Sheet, which is enough to prove the concept without adding a live webhook + Zapier account dependency to the critical path.

Config/assumptions to seed the data generator (defaults below — flag anything that should change):
- **Total annual revenue: ~$15M**, split roughly 60/40 across subsidiaries — Lumin Light USA ~$9M, Lumin Light Nigeria ~$6M (USA skews higher as HQ, holding more of the large multilateral/government relationships)
- **Time period: trailing 12 months** — September 2025 through August 2026
- **Warehouses: 2, one per subsidiary** — e.g., Houston, TX (USA) and Lagos, Nigeria (regional) — both plausible logistics hubs for this kind of product
- **Rough deal size ranges by product tier** (per institutional order, reflecting tier price point and typical order volume):
  - Sol 1: $5K–$150K
  - Sol 2: $10K–$200K
  - Sol 3: $15K–$250K
  - Sol 4: $50K–$750K
  - Sol 5: $75K–$1M

## Architecture

- **Python** for data generation and cleaning
- **Google Sheets** as the data layer the dashboard reads from — stands in for the real Zapier/Make → Sheets pipeline a live client version would use
- **Streamlit** for the app itself (dashboard + code lives in one place), including the manual refresh control
- **GitHub** for version control — this repo can be public, since nothing in it is real or sensitive
- **Streamlit Community Cloud** for hosting — free, deploys from the GitHub repo, public is fine here (unlike the real Be Girl version, which would need to be private)

## Build sequence

1. Confirm the open items above (revenue split, warehouse locations, deal size ranges)
2. Generate the synthetic datasets and load them into Google Sheets, for all three pillars
3. Build the Streamlit app — three pillars, the metrics listed above, reading from the Sheets, with a refresh button
4. Polish: README, clean repo, live deployed link
5. Publish — public GitHub repo + live Streamlit link

## Explicitly out of scope

- Any real Be Girl data, credentials, or system connections
- Any content that should live in the Be Girl Dashboard Project folder instead
- True real-time/continuous polling — a refresh-on-demand model is the realistic and sufficient choice here
- A live webhook-triggered Zapier refresh — noted above as a v2/stretch idea, not v1
