"""
Generates the Sales tab: one row per deal (open pipeline + closed won/lost).

Design notes (the non-obvious bits):

- Each deal's dollar VALUE is sampled first (from the spec's per-product
  ranges), and UNITS are derived from it (value / unit_price). That's
  backwards from how a real sales rep would think about it (units first,
  price follows), but it's the simplest way to respect the spec's given
  dollar ranges while still producing a unit count for inventory to use.

- Closed deals (Won/Lost) get their close date placed inside the current
  12-month dashboard window, so "deals won YTD" has a clean population to
  sum. Open deals get a created_date some days in the past and an
  expected_close_date that follows from their stage in the sales cycle —
  so a deal further along (Negotiation) is naturally closer to its
  expected close date than one still in Prospecting.
"""

import random
import datetime
import pandas as pd

import config

random.seed(config.RANDOM_SEED)

BUYER_TYPE_WEIGHTS = {"Government": 0.30, "Distributor": 0.30, "NGO": 0.25, "Multilateral": 0.15}

BUYER_NAMES = {
    "Government": [
        "Government of Kenya", "Government of Chad", "Government of Somalia",
        "Government of South Sudan", "Government of Yemen", "Government of Bangladesh",
        "Government of Haiti", "Government of Pakistan", "Government of Ethiopia",
        "Government of Mozambique", "Government of Nepal", "Government of Uganda",
        "Government of the Philippines", "Government of Honduras", "Government of Fiji",
    ],
    "Distributor": [
        "SunPath Distribution Ltd.", "Meridian Energy Supply Co.", "BrightWay Traders",
        "Solaris Import & Distribution", "Horizon Power Goods", "Equator Trading Group",
        "Radiant Supply Partners", "Coastal Energy Distributors", "Vantage Power Co.",
        "Northstar Energy Trading",
    ],
    "NGO": [
        "Mercy Horizon Relief", "Global Shelter Initiative", "Bridge Relief International",
        "Lifeline Response Network", "Open Hands Global", "Clearwater Aid Alliance",
        "Foundation for Displaced Communities", "Beacon Relief Corps", "SafeHaven Partners",
        "Common Ground Relief",
    ],
    "Multilateral": [
        "United Relief Agency (URA)", "Global Displacement Fund (GDF)",
        "International Shelter Coalition (ISC)", "World Emergency Response Council (WERC)",
        "Cross-Border Aid Commission (CBAC)", "Federated Humanitarian Assembly (FHA)",
    ],
}

STAGE_PROGRESS_BREAKPOINTS = [
    (0.25, "Prospecting"),
    (0.50, "Qualification"),
    (0.75, "Proposal"),
    (1.01, "Negotiation"),
]


def pick_subsidiary():
    weights = [config.ANNUAL_REVENUE_TARGET[s] for s in config.SUBSIDIARIES]
    return random.choices(config.SUBSIDIARIES, weights=weights, k=1)[0]


def pick_buyer_type():
    return random.choices(list(BUYER_TYPE_WEIGHTS), weights=list(BUYER_TYPE_WEIGHTS.values()), k=1)[0]


def pick_product():
    names = list(config.PRODUCTS)
    weights = [config.PRODUCTS[p]["selection_weight"] for p in names]
    return random.choices(names, weights=weights, k=1)[0]


def stage_from_progress(fraction_elapsed):
    for threshold, stage in STAGE_PROGRESS_BREAKPOINTS:
        if fraction_elapsed < threshold:
            return stage
    return "Negotiation"


def win_rate_for(buyer_type):
    return config.BASE_WIN_RATE + config.WIN_RATE_ADJUSTMENT[buyer_type]


def generate_deal(deal_id, period, subsidiary=None):
    """period is 'prior' or 'current' for a closed deal, or None for open pipeline.
    Pass subsidiary explicitly when generating deals toward a per-subsidiary
    revenue target; otherwise one is picked at random (weighted by revenue split)."""
    if subsidiary is None:
        subsidiary = pick_subsidiary()
    buyer_type = pick_buyer_type()
    buyer_name = random.choice(BUYER_NAMES[buyer_type])
    product = pick_product()

    low, high = config.PRODUCTS[product]["deal_value_range"]
    deal_value = round(random.uniform(low, high), -2)  # round to nearest $100

    unit_price = config.PRODUCTS[product]["unit_price"]
    unit_cost = config.PRODUCTS[product]["unit_cost"]
    quantity = max(1, round(deal_value / unit_price))

    cycle_low, cycle_high = config.SALES_CYCLE_DAYS[buyer_type]
    cycle_days = random.randint(cycle_low, cycle_high)

    if period in ("prior", "current"):
        period_start, period_end = {
            "prior": (config.PRIOR_PERIOD_START, config.PRIOR_PERIOD_END),
            "current": (config.CURRENT_PERIOD_START, config.TODAY),
        }[period]
        span_days = (period_end - period_start).days
        actual_close_date = period_start + datetime.timedelta(days=random.randint(0, span_days))
        created_date = actual_close_date - datetime.timedelta(days=cycle_days)
        expected_close_date = actual_close_date
        won = random.random() < win_rate_for(buyer_type)
        status = "Won" if won else "Lost"
        stage = ""  # closed deals have no stage — status (Won/Lost) covers that
        probability = 1.0 if won else 0.0
    else:
        days_elapsed = random.randint(5, cycle_days)
        created_date = config.TODAY - datetime.timedelta(days=days_elapsed)
        expected_close_date = created_date + datetime.timedelta(days=cycle_days)
        actual_close_date = None
        status = "Open"
        stage = stage_from_progress(days_elapsed / cycle_days)
        probability = config.STAGE_PROBABILITY[stage]

    return {
        "deal_id": f"DEAL-{deal_id:04d}",
        "subsidiary": subsidiary,
        "buyer_type": buyer_type,
        "buyer_name": buyer_name,
        "product": product,
        "quantity": quantity,
        "unit_price": unit_price,
        "unit_cost": unit_cost,
        "deal_value": deal_value,
        "status": status,
        "stage": stage,
        "probability": probability,
        "weighted_value": round(deal_value * probability, 2),
        "created_date": created_date.isoformat(),
        "expected_close_date": expected_close_date.isoformat(),
        "actual_close_date": actual_close_date.isoformat() if actual_close_date else "",
    }


def generate_closed_deals_toward_target(deal_id, period, subsidiary, target_revenue):
    """Keep generating deals (a realistic win/lose mix) for one subsidiary/period
    until Closed Won value reaches target_revenue. Returns (deals, next_deal_id)."""
    deals = []
    won_total = 0.0
    while won_total < target_revenue:
        deal = generate_deal(deal_id, period=period, subsidiary=subsidiary)
        deals.append(deal)
        deal_id += 1
        if deal["status"] == "Won":
            won_total += deal["deal_value"]
    return deals, deal_id


def generate_sales_data():
    deals = []
    deal_id = 1

    for subsidiary in config.SUBSIDIARIES:
        current_target = config.ANNUAL_REVENUE_TARGET[subsidiary]
        prior_target = current_target * config.PRIOR_PERIOD_REVENUE_FACTOR

        prior_deals, deal_id = generate_closed_deals_toward_target(deal_id, "prior", subsidiary, prior_target)
        deals.extend(prior_deals)

        current_deals, deal_id = generate_closed_deals_toward_target(deal_id, "current", subsidiary, current_target)
        deals.extend(current_deals)

    for _ in range(config.OPEN_DEALS):
        deals.append(generate_deal(deal_id, period=None))
        deal_id += 1

    df = pd.DataFrame(deals)
    df = df.sort_values("created_date").reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = generate_sales_data()
    print(df.head(10).to_string())
    print(f"\n{len(df)} deals generated")
    won = df[df.status == "Won"]
    lost = df[df.status == "Lost"]
    print(f"Won: {len(won)} deals, ${won.deal_value.sum():,.0f}")
    print(f"Lost: {len(lost)} deals")
    print(f"Win rate: {len(won) / (len(won) + len(lost)):.1%}")

    current_won = won[won.actual_close_date >= config.CURRENT_PERIOD_START.isoformat()]
    prior_won = won[won.actual_close_date < config.CURRENT_PERIOD_START.isoformat()]
    print(f"Current period Closed Won: ${current_won.deal_value.sum():,.0f}")
    print(f"Prior period Closed Won:   ${prior_won.deal_value.sum():,.0f}")
