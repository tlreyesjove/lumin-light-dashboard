# Project spec

## The company

**Lumin Light** is a fictional B2B company selling portable solar lighting
products to institutional buyers — governments, NGOs, multilateral agencies,
and distributors — for humanitarian aid, disaster response, and off-grid
communities. Pure B2B, no direct-to-consumer, sold via tender and direct
sales. Around 30 employees.

Two entities:
- **Lumin Light USA** (parent/HQ)
- **Lumin Light Nigeria** (regional subsidiary)

### Products — the Sol line

Five tiers, each with different pricing, margin, and expected order volume:

| Product | Positioning |
|---|---|
| Sol 1 | Pocket-sized, lowest cost, highest volume — personal preparedness |
| Sol 2 | Basic off-grid household lighting, affordable |
| Sol 3 | Portable, with integrated phone charging |
| Sol 4 | Modular, built for large-scale emergency deployment |
| Sol 5 | High-efficiency, extended runtime — shelters and facilities (premium, lowest volume) |

### Buyer types

Government, Distributor, NGO, and Multilaterals (UN agencies and similar).

## What the dashboard covers

A single-source-of-truth view for company leadership, spanning three areas:

**Sales** — pipeline weighted value vs. target, deals won YTD vs. target,
deals closing this quarter, win rate overall and by buyer type.

**Finance** — revenue by entity, revenue growth, margin by product tier,
EBIT/EBITDA/net income, cash position and runway, budget vs. actual.

**Inventory** — stock on hand by product and warehouse, and reorder alerts
that factor in weighted open pipeline demand rather than just today's stock
count. A large, near-certain deal about to close can push a "reorder" flag
even if current stock looks healthy on its own — this is the one metric
that deliberately connects the sales and inventory data rather than
treating them as separate silos.

## Data approach

There's no real company behind this, so there's no live system to pull
from — but the pipeline is built the way a real integration would be, so
the architecture is genuine even though the data is synthetic.

In a real deployment, a company's underlying systems (accounting software,
a CRM, an inventory tool) rarely expose data in a form a dashboard can read
directly, and bespoke API integrations per system are expensive to build
and maintain. The common lightweight pattern instead: an automation tool
(e.g. Zapier or Make) polls each source on a schedule and writes the
results into a shared Google Sheet, which acts as a simple staging layer —
easy to inspect by hand, and one consistent format for a dashboard to read
regardless of how many systems feed into it.

This project mirrors that pattern exactly, minus the real source systems:
synthetic data is generated locally and pushed into a Google Sheet, playing
the role the automation tool's output would in production. The dashboard
reads from that Sheet, not from data baked into the app — so the only thing
that would change to make this "real" is swapping the data-generation step
for a live automation feeding the same Sheet structure.

The dashboard reloads data on open and offers a manual refresh button, since
data at this frequency (daily at most) doesn't need continuous polling.

### Assumptions behind the synthetic data

- **Total annual revenue:** ~$15M, split roughly 60/40 USA/Nigeria
- **Time period:** trailing 12 months (Sept 2025–Aug 2026)
- **Warehouses:** one per entity (Houston, TX / Lagos, Nigeria)
- **Deal size ranges by product tier** (per institutional order):
  - Sol 1: $5K–$150K
  - Sol 2: $10K–$200K
  - Sol 3: $15K–$250K
  - Sol 4: $50K–$750K
  - Sol 5: $75K–$1M

## Architecture

- **Python** for data generation and transformation
- **Google Sheets** as the data layer the dashboard reads from
- **Streamlit** for the app itself, including manual refresh
- **GitHub** for version control
- **Streamlit Community Cloud** for hosting

## Out of scope

- True real-time/continuous data polling — refresh-on-demand is sufficient
  for data that changes at most daily
- A live webhook-triggered automation refresh — technically possible, but
  unnecessary complexity without a real source system behind it
