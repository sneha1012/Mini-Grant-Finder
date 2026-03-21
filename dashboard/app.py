"""
Mini-Grant Finder Dashboard — Streamlit web application.

A clean, professional dashboard for Delta Rising Foundation's
grant discovery pipeline. Displays scored grants with filters,
metrics, deadline alerts, and detailed views.

Run with: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

import streamlit as st
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.data_loader import (
    load_dashboard_data,
    get_summary_metrics,
    get_program_distribution,
    get_type_distribution,
    get_deadline_timeline,
)
from dashboard.components.metrics import render_metrics_row
from dashboard.components.grant_table import render_grant_table
from dashboard.components.filters import render_filters
from dashboard.pages.grant_detail import render_grant_detail
from dashboard.pages.deadline_alerts import render_deadline_alerts

# --- Page Configuration ---
st.set_page_config(
    page_title="Mini-Grant Finder | Delta Rising Foundation",
    page_icon="\U0001F331",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Load Custom CSS ---
css_path = Path(__file__).parent / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def main():
    """Main dashboard application."""

    # --- Header ---
    st.markdown(
        """
        <div class="dashboard-header">
            <h1>Mini-Grant Finder</h1>
            <p class="subtitle">Delta Rising Foundation &mdash; Automated Grant Discovery Dashboard</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Sidebar ---
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center; padding: 0.5rem 0 1rem;">
                <span style="font-size: 2.2rem;">&#127793;</span>
                <div style="color: #fff; font-size: 1.1rem; font-weight: 700; letter-spacing: 0.5px; margin-top: 0.2rem;">
                    Delta Rising
                </div>
                <div style="color: rgba(255,255,255,0.6); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1.5px;">
                    Foundation
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown("### Navigation")
        page = st.radio(
            "View",
            [
                "Dashboard",
                "Deadline Alerts",
                "Grant Details",
            ],
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("### About")
        st.markdown(
            """
            **Delta Rising Foundation**
            Garden Grove, California
            EIN: 84-2889631

            Accelerating science-based systemic
            solutions and evolving the art of
            sustainable culture.

            *$0 operating cost — fully open source*
            """
        )

        st.markdown("---")
        st.markdown(
            '<div style="text-align:center; opacity:0.5; font-size:0.7rem;">'
            "Built with Streamlit + scikit-learn<br>"
            "github.com/sneha1012/Mini-Grant-Finder"
            "</div>",
            unsafe_allow_html=True,
        )

    # --- Load Data ---
    grants = load_dashboard_data()

    if not grants:
        st.warning(
            "No grant data found. Run the pipeline first: "
            "`python -m src.main`"
        )
        st.info(
            "The dashboard will automatically load research data "
            "from the CSV files."
        )
        # Try loading from research CSVs directly
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

    # --- Route to Pages ---
    if page == "Dashboard":
        render_dashboard(grants)
    elif page == "Deadline Alerts":
        render_deadline_alerts(grants)
    elif page == "Grant Details":
        render_grant_detail(grants)


def render_dashboard(grants):
    """Render the main dashboard view with metrics, charts, and table."""

    # --- Metrics Row ---
    metrics = get_summary_metrics(grants)
    render_metrics_row(metrics)

    st.markdown("")

    # --- Charts Row ---
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
            chart_data = {
                display_names.get(k, k): v
                for k, v in prog_dist.items()
            }
            df = pd.DataFrame({
                "Program": list(chart_data.keys()),
                "Grants": list(chart_data.values()),
            })
            st.bar_chart(df.set_index("Program"), color="#2d8a56")
        else:
            st.caption("Run scoring to see program distribution")

    with chart_col2:
        st.markdown("#### Grants by Type")
        type_dist = get_type_distribution(grants)
        if type_dist:
            df = pd.DataFrame({
                "Type": list(type_dist.keys()),
                "Count": list(type_dist.values()),
            })
            st.bar_chart(df.set_index("Type"), color="#4caf50")

    with chart_col3:
        st.markdown("#### Upcoming Deadlines")
        timeline = get_deadline_timeline(grants, days_ahead=90)
        if timeline:
            for item in timeline[:6]:
                days = item["days_left"]
                if days <= 7:
                    indicator = "&#128308;"  # red
                elif days <= 30:
                    indicator = "&#128992;"  # orange
                else:
                    indicator = "&#128994;"  # green

                st.markdown(
                    f"{indicator} **{item['deadline'].strftime('%b %d')}** "
                    f"&mdash; {item['name'][:45]}"
                    f"{'...' if len(item['name']) > 45 else ''}",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No upcoming deadlines found")

    st.markdown("---")

    # --- Filters ---
    filtered_grants = render_filters(grants)

    # --- Grant Table ---
    st.markdown(
        f'<div style="display:flex; justify-content:space-between; align-items:baseline;">'
        f'<h3 style="margin:0;">Grant Opportunities</h3>'
        f'<span style="color:#7a9188; font-size:0.9rem;">'
        f'Showing {len(filtered_grants)} of {len(grants)} grants</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("")
    render_grant_table(filtered_grants)


if __name__ == "__main__":
    main()
