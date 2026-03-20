"""
Grant table component for the dashboard.

Renders an interactive, sortable table of grant opportunities
with color-coded deadlines and relevance scores.
"""

import pandas as pd
import streamlit as st

from src.models.grant import Grant


def render_grant_table(grants: list[Grant]) -> None:
    """
    Render the main grant table with all opportunities.

    Displays a sortable dataframe with key grant information,
    color-coded by urgency and relevance.

    Args:
        grants: Filtered list of Grant objects to display
    """
    if not grants:
        st.info("No grants match the current filters.")
        return

    # Convert to DataFrame for display
    rows = []
    for grant in grants:
        rows.append({
            "Priority": _priority_badge(grant.priority.value),
            "Grant Name": grant.name,
            "Amount": grant.amount_display,
            "Deadline": _format_deadline(grant),
            "Score": f"{grant.relevance_score:.0f}",
            "Programs": ", ".join(
                _short_program_name(p) for p in grant.matched_programs[:2]
            ) if grant.matched_programs else "—",
            "Status": grant.status.value.replace("_", " ").title(),
            "Type": grant.grant_type.value.replace("_", " ").title(),
            "Location": _truncate(grant.geographic_scope, 25),
            "URL": grant.url,
        })

    df = pd.DataFrame(rows)

    # Display as interactive dataframe
    st.dataframe(
        df,
        column_config={
            "Priority": st.column_config.TextColumn("Priority", width="small"),
            "Grant Name": st.column_config.TextColumn("Grant Name", width="large"),
            "Amount": st.column_config.TextColumn("Amount", width="medium"),
            "Deadline": st.column_config.TextColumn("Deadline", width="medium"),
            "Score": st.column_config.TextColumn("Score", width="small"),
            "Programs": st.column_config.TextColumn("Programs", width="medium"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Type": st.column_config.TextColumn("Type", width="medium"),
            "Location": st.column_config.TextColumn("Location", width="medium"),
            "URL": st.column_config.LinkColumn("Link", width="small", display_text="Apply"),
        },
        hide_index=True,
        use_container_width=True,
        height=min(len(rows) * 40 + 50, 600),
    )

    # Download button
    csv_data = df.to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        data=csv_data,
        file_name="delta_grants_export.csv",
        mime="text/csv",
    )


def _priority_badge(priority: str) -> str:
    """Format priority as a badge-style string."""
    badges = {
        "urgent": "URGENT",
        "high": "HIGH",
        "medium": "MED",
        "low": "LOW",
        "monitor": "WATCH",
    }
    return badges.get(priority, priority.upper())


def _format_deadline(grant: Grant) -> str:
    """Format deadline with urgency context."""
    if grant.deadline:
        days = grant.days_until_deadline
        date_str = grant.deadline.strftime("%b %d, %Y")
        if days is not None:
            if days < 0:
                return f"{date_str} (expired)"
            elif days == 0:
                return f"{date_str} (TODAY)"
            elif days <= 7:
                return f"{date_str} ({days}d left)"
            elif days <= 30:
                return f"{date_str} ({days}d)"
            return date_str
    return grant.deadline_text if grant.deadline_text else "—"


def _short_program_name(program: str) -> str:
    """Shorten program names for table display."""
    shorts = {
        "ai_climate_tools": "AI Climate",
        "resilience_nursery": "Nursery",
        "more_shade": "Shade",
        "cbecn": "CBECN",
    }
    return shorts.get(program, program[:15])


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return "—"
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "..."
