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

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.data_loader import load_dashboard_data, get_summary_metrics
from dashboard.components.metrics import render_metrics_row
from dashboard.components.grant_table import render_grant_table
from dashboard.components.filters import render_filters
from dashboard.pages.grant_detail import render_grant_detail
from dashboard.pages.deadline_alerts import render_deadline_alerts

# --- Page Configuration ---
st.set_page_config(
    page_title="Mini-Grant Finder | Delta Rising Foundation",
    page_icon="🌱",
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
            <p class="subtitle">Delta Rising Foundation — Automated Grant Discovery</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### Navigation")
        page = st.radio(
            "View",
            ["Dashboard", "Deadline Alerts", "Grant Details"],
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("### About")
        st.markdown(
            """
            **Delta Rising Foundation**
            Garden Grove, California
            EIN: 84-2889631

            This tool automatically finds and scores
            grant opportunities relevant to our mission.

            *$0 operating cost*
            """
        )

        st.markdown("---")
        st.markdown(
            "<small>Built with Streamlit + scikit-learn</small>",
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
            "Or the dashboard will automatically load research data "
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
    """Render the main dashboard view."""

    # --- Metrics Row ---
    metrics = get_summary_metrics(grants)
    render_metrics_row(metrics)

    st.markdown("---")

    # --- Filters ---
    filtered_grants = render_filters(grants)

    # --- Grant Table ---
    st.markdown(f"### Showing {len(filtered_grants)} of {len(grants)} grants")
    render_grant_table(filtered_grants)


if __name__ == "__main__":
    main()
