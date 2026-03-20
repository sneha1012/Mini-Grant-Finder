"""
Metrics card components for the dashboard.

Renders the top-row KPI cards showing total grants, urgent deadlines,
high-relevance matches, and total funding discovered.
"""

import streamlit as st


def render_metrics_row(metrics: dict) -> None:
    """
    Render the metrics cards row at the top of the dashboard.

    Args:
        metrics: Dict with keys: total_grants, urgent_count,
                 high_relevance, new_today, total_funding, avg_score
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{metrics.get('total_grants', 0)}</div>
                <div class="metric-label">Total Grants</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        urgent = metrics.get("urgent_count", 0)
        urgent_class = "metric-urgent" if urgent > 0 else ""
        st.markdown(
            f"""
            <div class="metric-card {urgent_class}">
                <div class="metric-value">{urgent}</div>
                <div class="metric-label">Urgent Deadlines</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{metrics.get('high_relevance', 0)}</div>
                <div class="metric-label">High Relevance</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        funding = metrics.get("total_funding", 0)
        if funding >= 1_000_000:
            funding_display = f"${funding/1_000_000:.1f}M"
        elif funding >= 1_000:
            funding_display = f"${funding/1_000:.0f}K"
        else:
            funding_display = f"${funding:,.0f}"

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{funding_display}</div>
                <div class="metric-label">Total Funding Found</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
