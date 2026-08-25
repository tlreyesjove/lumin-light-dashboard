"""
Central place for every assumption that feeds the synthetic data generator.

Nothing in here is "real" — it's all made up to produce a plausible-looking
B2B solar lighting business. If a number here looks wrong, change it here
and re-run the generator scripts; nothing else needs to change.
"""

import datetime

# ---------------------------------------------------------------------------
# Time window
# ---------------------------------------------------------------------------
# The dashboard's "current" view covers the trailing 12 months.
TODAY = datetime.date(2026, 8, 25)
CURRENT_PERIOD_START = datetime.date(2025, 9, 1)
CURRENT_PERIOD_END = datetime.date(2026, 8, 31)

# One prior 12-month window, so "revenue growth vs. prior period" has
# something real to compare against instead of a made-up single number.
PRIOR_PERIOD_START = datetime.date(2024, 9, 1)
PRIOR_PERIOD_END = datetime.date(2025, 8, 31)

# ---------------------------------------------------------------------------
# Company structure
# ---------------------------------------------------------------------------
SUBSIDIARIES = ["Lumin Light USA", "Lumin Light Nigeria"]

# Annual revenue target split (current period). USA skews higher — HQ,
# holds more of the large multilateral/government relationships.
ANNUAL_REVENUE_TARGET = {
    "Lumin Light USA": 9_000_000,
    "Lumin Light Nigeria": 6_000_000,
}
TOTAL_REVENUE_TARGET = sum(ANNUAL_REVENUE_TARGET.values())  # $15M

WAREHOUSES = {
    "Lumin Light USA": {"warehouse": "Houston, TX", "subsidiary": "Lumin Light USA"},
    "Lumin Light Nigeria": {"warehouse": "Lagos, Nigeria", "subsidiary": "Lumin Light Nigeria"},
}

BUYER_TYPES = ["Government", "Distributor", "NGO", "Multilateral"]

# ---------------------------------------------------------------------------
# Products — the Sol line
# ---------------------------------------------------------------------------
# unit_price / unit_cost are MY assumptions (not given in the spec) — needed
# to turn a deal's total dollar value into a plausible unit quantity, and to
# get realistic margins that widen from Sol 1 to Sol 5. Flag if these feel off.
#
# deal_value_range = total order value range from the spec (this is what's
# actually sampled per deal — quantity is *derived* from it, not the other
# way around).
PRODUCTS = {
    "Sol 1": {
        "positioning": "Pocket-sized, lowest cost, highest volume — personal preparedness",
        "deal_value_range": (5_000, 150_000),
        "unit_price": 8,
        "unit_cost": 5.20,      # ~35% gross margin
        "selection_weight": 0.35,
    },
    "Sol 2": {
        "positioning": "Basic off-grid household lighting, affordable",
        "deal_value_range": (10_000, 200_000),
        "unit_price": 25,
        "unit_cost": 15.75,     # ~37% gross margin
        "selection_weight": 0.25,
    },
    "Sol 3": {
        "positioning": "Portable, with integrated phone charging",
        "deal_value_range": (15_000, 250_000),
        "unit_price": 60,
        "unit_cost": 35.40,     # ~41% gross margin
        "selection_weight": 0.20,
    },
    "Sol 4": {
        "positioning": "Modular, built for large-scale emergency deployment",
        "deal_value_range": (50_000, 750_000),
        "unit_price": 350,
        "unit_cost": 189.00,    # ~46% gross margin
        "selection_weight": 0.12,
    },
    "Sol 5": {
        "positioning": "High-efficiency, extended runtime — shelters and facilities",
        "deal_value_range": (75_000, 1_000_000),
        "unit_price": 900,
        "unit_cost": 405.00,    # ~55% gross margin
        "selection_weight": 0.08,
    },
}

# ---------------------------------------------------------------------------
# Sales pipeline
# ---------------------------------------------------------------------------
# Stage only applies to OPEN deals — mutually exclusive with status
# (Won/Lost deals have no stage; that's what status is for). Each stage's
# win probability, per Tatiana:
STAGE_PROBABILITY = {
    "Prospecting": 0.10,
    "Qualification": 0.10,
    "Proposal": 0.50,
    "Negotiation": 0.90,
}
OPEN_STAGES = list(STAGE_PROBABILITY)

# Closed Won deals are generated per subsidiary/period by drawing deals
# until their cumulative value reaches a target (see generate_sales.py) —
# not by picking a fixed deal count, which turned out to be too noisy: a
# handful of large Sol 4/5 deals landing in one period by chance could
# swing that period's total by 20%+. Targeting revenue directly keeps
# deal-by-deal randomness (product, buyer, exact value) while controlling
# the metric that actually matters (period revenue, and the growth
# between periods).
#
# Prior-period target as a fraction of current — this is what produces
# "revenue growth vs. prior period," not a separately-invented growth rate.
PRIOR_PERIOD_REVENUE_FACTOR = 0.87

OPEN_DEALS = 90

# Base win rate for a closed deal; nudged up/down per buyer type below.
BASE_WIN_RATE = 0.32
WIN_RATE_ADJUSTMENT = {
    "Government": -0.06,   # competitive tenders, harder to win
    "Distributor": 0.10,   # repeat channel relationships
    "NGO": 0.00,
    "Multilateral": -0.02,
}

# Typical days from deal creation to expected close, by buyer type
# (government tenders move slower than distributor reorders).
SALES_CYCLE_DAYS = {
    "Government": (120, 270),
    "Distributor": (30, 90),
    "NGO": (45, 120),
    "Multilateral": (90, 200),
}

# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------
BLENDED_OPEX_PCT_OF_REVENUE = 0.32   # opex as % of revenue, before EBIT
STARTING_CASH_BALANCE = 2_200_000    # cash balance at PRIOR_PERIOD_START
AR_LAG_DAYS = 35                     # institutional buyers pay slowly — cash lags revenue

# Budget vs. actual noise (budget set before the year started, so actuals
# naturally drift from it).
BUDGET_VARIANCE_PCT = 0.10

# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
# Lead time = how long it takes to receive a replenishment order (e.g. an
# order of ~100,000 units) after placing it. Tatiana's assumption: 1 month,
# same for average and worst case. Kept as two separate constants (not one)
# so this still works if avg/max lead time ever need to diverge — e.g. the
# Nigeria warehouse taking longer on a bad shipping month than usual.
AVG_LEAD_TIME_MONTHS = 1
MAX_LEAD_TIME_MONTHS = 1

RANDOM_SEED = 42
