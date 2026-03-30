"""
Grant Finder Dashboard — Delta Rising Foundation

Run with: streamlit run dashboard/app.py
"""

import base64
import sys
from datetime import date
from pathlib import Path

import streamlit as st
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.data_loader import (
    load_dashboard_data,
    get_program_distribution,
    get_type_distribution,
    get_deadline_timeline,
)
from dashboard.components.grant_table import render_grant_table
from dashboard.components.filters import render_filters
from dashboard.pages.grant_detail import render_grant_detail
from dashboard.pages.deadline_alerts import render_deadline_alerts

ASSETS = Path(__file__).parent / "assets"


def _b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# --- Page Config ---
st.set_page_config(
    page_title="Grant Finder | Delta Rising Foundation",
    page_icon=str(ASSETS / "logo.webp") if (ASSETS / "logo.webp").exists() else None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- CSS ---
css_path = Path(__file__).parent / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def main():
    hero_path = ASSETS / "hero.jpg"
    logo_path = ASSETS / "logo.webp"

    # Build logo + org name block
    brand_html = ""
    if logo_path.exists():
        logo_b64 = _b64(logo_path)
        brand_html = (
            f'<img src="data:image/webp;base64,{logo_b64}" '
            f'class="hero-logo" alt="Delta Rising Foundation">'
        )

    if hero_path.exists():
        hero_b64 = _b64(hero_path)
        bg_style = (
            f"background-image: "
            f"linear-gradient(180deg, rgba(10,20,15,0.25) 0%, rgba(10,20,15,0.45) 100%),"
            f"url('data:image/jpeg;base64,{hero_b64}');"
        )
    else:
        bg_style = "background: linear-gradient(135deg, #1a3a2a, #2c5e3f);"

    st.markdown(
        f"""
        <div class="hero" style="{bg_style}">
            <div class="hero-top">
                {brand_html}
                <div class="hero-contact">
                    <a href="https://www.deltarisingfoundation.org" target="_blank">Website</a>
                    <span class="hero-divider"></span>
                    <a href="mailto:info@deltarisingfoundation.org">Email</a>
                    <span class="hero-divider"></span>
                    <a href="tel:+13103477659">(310) 347-7659</a>
                </div>
            </div>
            <div class="hero-content">
                <h1 class="hero-title">Grant Finder</h1>
                <p class="hero-subtitle">Automated Grant Discovery Dashboard</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Load Data ---
    grants = load_dashboard_data()

    if not grants:
        st.warning("No grant data found. Run the pipeline first: `python -m src.main`")
        try:
            from src.loaders.csv_loader import load_all_research_data
            from src.pipeline.processor import process_grants
            raw = load_all_research_data()
            grants = process_grants(raw)
            if grants:
                st.success(f"Loaded {len(grants)} grants from research data.")
        except Exception as e:
            st.error(f"Could not load research data: {e}")
            return

    if not grants:
        return

    # --- Tab Navigation ---
    tab1, tab2, tab3 = st.tabs(["Dashboard", "Deadline Alerts", "Grant Details"])

    with tab1:
        render_dashboard(grants)
    with tab2:
        render_deadline_alerts(grants)
    with tab3:
        render_grant_detail(grants)

    # --- Footer ---
    st.markdown(
        '<div class="footer">'
        "Delta Rising Foundation &middot; Garden Grove, CA &middot; EIN 84-2889631<br>"
        '<a href="https://www.deltarisingfoundation.org" target="_blank">'
        "deltarisingfoundation.org</a> &middot; "
        "<em>Accelerating science-based systemic solutions and evolving "
        "the art of sustainable culture.</em>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_dashboard(grants):
    # Filters first — right below tabs
    filtered_grants = render_filters(grants)

    # Grant count + table header
    st.markdown(
        f'<div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:0.5rem;">'
        f'<h3 style="margin:0; border:none; padding:0;">Grant Opportunities</h3>'
        f'<span style="color:#8a8a7a; font-size:0.8rem;">'
        f'Showing {len(filtered_grants)} of {len(grants)} grants</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("")
    render_grant_table(filtered_grants)

    st.markdown("---")

    # Charts row below the table
    chart_col1, chart_col2, chart_col3 = st.columns([1, 1, 1])

    with chart_col1:
        st.markdown("#### Grants by Program")
        prog_dist = get_program_distribution(grants)
        if prog_dist:
            display_names = {
                "ai_climate_tools": "AI Climate Tools",
                "resilience_nursery": "Resilience Nursery",
                "more_shade": "More Shade",
                "cbecn": "CBECN",
            }
            chart_data = {display_names.get(k, k): v for k, v in prog_dist.items()}
            df = pd.DataFrame({"Program": list(chart_data.keys()), "Grants": list(chart_data.values())})
            st.bar_chart(df.set_index("Program"), color="#3a6b4a")
        else:
            st.caption("Run scoring to see program distribution")

    with chart_col2:
        st.markdown("#### Grants by Type")
        type_dist = get_type_distribution(grants)
        if type_dist:
            df = pd.DataFrame({"Type": list(type_dist.keys()), "Count": list(type_dist.values())})
            st.bar_chart(df.set_index("Type"), color="#4a6741")

    with chart_col3:
        st.markdown("#### Upcoming Deadlines")
        timeline = get_deadline_timeline(grants, days_ahead=90)
        if timeline:
            for item in timeline[:6]:
                days = item["days_left"]
                if days <= 7:
                    dot_color = "#9e3b33"
                elif days <= 30:
                    dot_color = "#8a7030"
                else:
                    dot_color = "#3a6b4a"

                name = item['name'][:40]
                ellipsis = '...' if len(item['name']) > 40 else ''
                st.markdown(
                    f'<div class="deadline-item">'
                    f'<span style="display:inline-block;width:7px;height:7px;'
                    f'border-radius:50%;background:{dot_color};margin-right:8px;'
                    f'vertical-align:middle;"></span>'
                    f'<span class="deadline-date">{item["deadline"].strftime("%b %d")}</span>'
                    f' &mdash; <span class="deadline-name">{name}{ellipsis}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No upcoming deadlines found")


if __name__ == "__main__":
    main()
