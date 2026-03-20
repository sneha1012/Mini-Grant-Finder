"""
Filter components for the dashboard.

Provides sidebar and inline filter controls for narrowing down
the grant list by program, deadline, amount, type, and status.
"""

from datetime import date, timedelta

import streamlit as st

from src.models.grant import Grant, GrantType, Priority


# Display names for programs
PROGRAM_DISPLAY = {
    "ai_climate_tools": "AI Climate Tools",
    "resilience_nursery": "Resilience Nursery",
    "more_shade": "More Shade",
    "cbecn": "CBECN",
}


def render_filters(grants: list[Grant]) -> list[Grant]:
    """
    Render filter controls and return the filtered grant list.

    Displays filters in columns above the table for quick filtering
    without scrolling to the sidebar.

    Args:
        grants: Full list of grants to filter

    Returns:
        Filtered list of grants
    """
    with st.expander("Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)

        # Program filter
        with col1:
            all_programs = set()
            for grant in grants:
                for prog in grant.matched_programs:
                    all_programs.add(prog)

            program_options = ["All Programs"] + sorted(all_programs)
            selected_program = st.selectbox(
                "Program",
                program_options,
                key="filter_program",
            )

        # Deadline filter
        with col2:
            deadline_options = [
                "All Deadlines",
                "Next 7 days",
                "Next 30 days",
                "Next 60 days",
                "Rolling/Open",
                "No deadline set",
            ]
            selected_deadline = st.selectbox(
                "Deadline",
                deadline_options,
                key="filter_deadline",
            )

        # Priority filter
        with col3:
            priority_options = ["All Priorities", "Urgent", "High", "Medium", "Low"]
            selected_priority = st.selectbox(
                "Priority",
                priority_options,
                key="filter_priority",
            )

        # Grant type filter
        with col4:
            type_options = ["All Types"] + sorted(set(
                g.grant_type.value.replace("_", " ").title()
                for g in grants
                if g.grant_type.value != "unknown"
            ))
            selected_type = st.selectbox(
                "Grant Type",
                type_options,
                key="filter_type",
            )

        # Relevance score slider
        col5, col6 = st.columns(2)
        with col5:
            min_score = st.slider(
                "Minimum Relevance Score",
                min_value=0,
                max_value=100,
                value=0,
                step=5,
                key="filter_score",
            )

        with col6:
            search_text = st.text_input(
                "Search grants",
                placeholder="Search by name, funder, or keyword...",
                key="filter_search",
            )

    # Apply filters
    filtered = grants

    # Program filter
    if selected_program != "All Programs":
        filtered = [
            g for g in filtered
            if selected_program in g.matched_programs
        ]

    # Deadline filter
    today = date.today()
    if selected_deadline == "Next 7 days":
        filtered = [
            g for g in filtered
            if g.deadline and 0 <= (g.deadline - today).days <= 7
        ]
    elif selected_deadline == "Next 30 days":
        filtered = [
            g for g in filtered
            if g.deadline and 0 <= (g.deadline - today).days <= 30
        ]
    elif selected_deadline == "Next 60 days":
        filtered = [
            g for g in filtered
            if g.deadline and 0 <= (g.deadline - today).days <= 60
        ]
    elif selected_deadline == "Rolling/Open":
        filtered = [
            g for g in filtered
            if g.status.value in ("rolling", "open") or not g.deadline
        ]
    elif selected_deadline == "No deadline set":
        filtered = [g for g in filtered if not g.deadline]

    # Priority filter
    if selected_priority != "All Priorities":
        priority_map = {
            "Urgent": "urgent",
            "High": "high",
            "Medium": "medium",
            "Low": "low",
        }
        target = priority_map.get(selected_priority, "")
        filtered = [g for g in filtered if g.priority.value == target]

    # Type filter
    if selected_type != "All Types":
        filtered = [
            g for g in filtered
            if g.grant_type.value.replace("_", " ").title() == selected_type
        ]

    # Score filter
    if min_score > 0:
        filtered = [g for g in filtered if g.relevance_score >= min_score]

    # Text search
    if search_text:
        search_lower = search_text.lower()
        filtered = [
            g for g in filtered
            if search_lower in g.name.lower()
            or search_lower in g.funder.lower()
            or search_lower in g.description.lower()
            or any(search_lower in fa.lower() for fa in g.focus_areas)
        ]

    return filtered
