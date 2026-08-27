"""
Brand colors and CSS, straight from Lumin Light Brand Guide.html — nothing
invented here, this file just makes those choices reusable in Streamlit.

Color roles, per the brand guide's usage rules:
- NAVY / NAVY_SECONDARY: primary text, headers, KPI numbers.
- AMBER: accent ONLY — one highlighted series, a CTA, never a base fill and
  never one of several category colors (the guide is explicit: "don't reuse
  status amber/red/green for branding or charts unrelated to alerts").
- STATUS_GOOD / STATUS_WARNING / STATUS_CRITICAL: reserved for the
  Inventory reorder alerts. Nowhere else.
- PRODUCT_COLORS: Sol 1-5 form a real ordinal sequence (entry-tier to
  premium), so they're a single blue ramp light-to-dark, ending at Navy
  Primary itself for Sol 5 — not five arbitrary hues.
- CLIENT_TYPE_COLORS: Institutional vs. Commercial is the two-category,
  one-highlighted-series case AMBER is meant for — Navy for the core
  (Institutional) business, Amber to make Commercial pop against it.
"""

import streamlit as st

NAVY = "#0B1F3A"
NAVY_SECONDARY = "#1E3A5F"
AMBER = "#F5A623"
SAND = "#FDE9C8"

PAGE_BG = "#F7F8FA"
CARD_BG = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT_SECONDARY = "#6B7280"

STATUS_GOOD = "#16A34A"
STATUS_WARNING = "#F59E0B"
STATUS_CRITICAL = "#DC2626"

# Ordinal ramp, Sol 1 (lightest) -> Sol 5 (Navy Primary) — light-mode contrast
# checked against white card backgrounds; each bar carries a text label too,
# so no slot relies on fill color alone to be legible.
PRODUCT_COLORS = {
    "Sol 1": "#9EC5F4",
    "Sol 2": "#6DA7EC",
    "Sol 3": "#2A78D6",
    "Sol 4": "#184F95",
    "Sol 5": "#0B1F3A",
}

# Client Type (Institutional/Commercial) is the exact "amber as accent,
# one series" case the brand guide describes: Navy for the core business
# (Institutional), Amber to make the smaller Commercial slice pop against it.
CLIENT_TYPE_COLORS = {
    "Institutional": NAVY,
    "Commercial": AMBER,
}

# Muted win/loss colors, per Tatiana — softer than the Inventory tab's
# STATUS_GOOD/STATUS_CRITICAL (which stay bright/saturated, reserved for
# reorder alerts). Deliberately a separate pair, not a reuse of those
# tokens, so changing this doesn't also change Inventory's alert colors.
WIN_LOSS_COLORS = {
    "Win": "#71AE79",
    "Loss": "#FB8B80",
}

STAGE_ORDER = ["Prospecting", "Qualification", "Proposal", "Negotiation"]


def inject_css():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"], [class*="st-emotion"], p, span, div, button, input, label {{
            font-family: 'Inter', -apple-system, sans-serif !important;
        }}
        .stApp {{
            background-color: {PAGE_BG};
        }}
        h1, h2, h3 {{
            color: {NAVY} !important;
            font-weight: 800 !important;
            font-family: 'Inter', -apple-system, sans-serif !important;
        }}
        [data-testid="stMetric"] {{
            background-color: {CARD_BG};
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 16px 20px;
        }}
        [data-testid="stMetricLabel"] {{
            color: {TEXT_SECONDARY} !important;
            font-weight: 600 !important;
        }}
        [data-testid="stMetricValue"] {{
            color: {NAVY} !important;
            font-weight: 700 !important;
        }}
        /* st.metric's delta always ships with a colored up/down arrow glyph
           next to the text — delta_color="off" removes the red/green color
           but not the arrow itself. Hiding the icon here (not just muting
           its color) is the only way to get delta text with no arrow at
           all, for cases like "% of annual target" that aren't a
           good/bad comparison and shouldn't look like one. */
        [data-testid="stMetricDelta"] svg {{
            display: none;
        }}
        [data-testid="stMetricDelta"] {{
            color: {TEXT_SECONDARY} !important;
        }}
        /* Bold whichever entity/tab is currently selected — covers both
           the tab bar (role="tab", aria-selected) and the entity selector
           (a segmented_control button whose kind flips to *Active when
           selected). The text sits in a nested <p>, which has its own
           font-weight that overrides the button's unless targeted directly. */
        [role="tab"][aria-selected="true"], [role="tab"][aria-selected="true"] p,
        button[kind="segmented_controlActive"], button[kind="segmented_controlActive"] p {{
            font-weight: 700 !important;
        }}
        /* Sales/Finance/Inventory tabs, restyled to match the entity
           selector's pill-button look (border, rounded, filled when
           active) instead of Streamlit's default plain text + thin
           underline — that default was easy to miss entirely sitting
           right below the bolder-looking entity selector. The light
           band behind them (tab-list) gives the row its own visual
           space instead of blending into the page. */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {{
            background-color: #EFF1F4;
            border-radius: 10px;
            padding: 6px;
            gap: 8px;
        }}
        [data-baseweb="tab-highlight"] {{
            display: none;
        }}
        [data-testid="stTab"] {{
            background-color: {CARD_BG};
            border: 1px solid {BORDER};
            border-radius: 20px !important;
            padding: 6px 16px !important;
            height: auto !important;
        }}
        [data-testid="stTab"] p {{
            color: {NAVY} !important;
            font-size: 13px;
        }}
        [data-testid="stTab"][aria-selected="true"] {{
            background-color: {NAVY} !important;
            border-color: {NAVY} !important;
        }}
        [data-testid="stTab"][aria-selected="true"] p {{
            color: white !important;
        }}
        /* Entity selector (Lumin Group Consolidated/USA/Nigeria), given
           the same light band treatment as the tabs below it, and a
           slightly larger font since it's the higher-level control of
           the two rows. */
        [role="radiogroup"] {{
            background-color: #EFF1F4;
            border-radius: 10px;
            padding: 6px;
            gap: 8px !important;
        }}
        [data-testid="stBaseButton-segmented_control"] p,
        [data-testid="stBaseButton-segmented_controlActive"] p {{
            font-size: 16px !important;
        }}
        /* Streamlit's default "selected" look for segmented_control is a
           translucent navy wash with navy text, not a solid fill — swap
           it for the same solid-navy/white-text treatment the tabs use,
           so both rows genuinely match. */
        [data-testid="stBaseButton-segmented_controlActive"] {{
            background-color: {NAVY} !important;
            border-color: {NAVY} !important;
        }}
        [data-testid="stBaseButton-segmented_controlActive"] p {{
            color: white !important;
        }}
        .lumin-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 3px solid {AMBER};
            padding-bottom: 16px;
            margin-bottom: 40px;
        }}
        .lumin-wordmark {{
            font-weight: 800;
            font-size: 28px;
            letter-spacing: -0.5px;
            color: {NAVY};
        }}
        .lumin-wordmark span {{ color: {AMBER}; }}
        .lumin-tagline {{
            font-size: 12px;
            color: {TEXT_SECONDARY};
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .status-pill {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            color: white;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(subtitle):
    st.markdown(
        f"""
        <div class="lumin-header">
            <div>
                <div class="lumin-wordmark">Lumin<span>&middot;</span>Light</div>
                <div class="lumin-tagline">Leadership Dashboard</div>
            </div>
            <div style="text-align:right; font-size:12px; color:{TEXT_SECONDARY};">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
