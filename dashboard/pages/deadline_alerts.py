"""
Deadline alerts page for the dashboard.

Shows upcoming grant deadlines organized by urgency with
visual timeline and countdown indicators.
"""

from datetime import date

import streamlit as st

from src.models.grant import Grant


def render_deadline_alerts(grants: list[Grant]) -> None:
    """
    Render the deadline alerts page.

    Shows grants organized by deadline urgency:
    - This Week (red)
    - Next 2 Weeks (orange)
    - This Month (yellow)
    - Upcoming (green)
    - Rolling / No Deadline (gray)

    Args:
        grants: List of all grants
    """
    st.markdown("### Deadline Alerts")
    st.markdown(
        "Upcoming grant deadlines organized by urgency. "
        "Stay on top of applications with this at-a-glance view."
    )

    today = date.today()

    # Categorize grants by deadline urgency
    this_week = []
    next_two_weeks = []
    this_month = []
    upcoming = []
    rolling = []
    no_deadline = []

    for grant in grants:
        if grant.deadline is None:
            if grant.status.value in ("rolling", "open"):
                rolling.append(grant)
            else:
                no_deadline.append(grant)
        else:
            days = (grant.deadline - today).days
            if days < 0:
                continue  # Skip expired
            elif days <= 7:
                this_week.append(grant)
            elif days <= 14:
                next_two_weeks.append(grant)
            elif days <= 30:
                this_month.append(grant)
            else:
                upcoming.append(grant)

    # Sort each group by deadline
    for group in [this_week, next_two_weeks, this_month, upcoming]:
        group.sort(key=lambda g: g.deadline or date.max)

    # Render each urgency section
    if this_week:
        _render_urgency_section(
            "This Week",
            this_week,
            color="#e74c3c",
            emoji="🔴",
        )

    if next_two_weeks:
        _render_urgency_section(
            "Next 2 Weeks",
            next_two_weeks,
            color="#e67e22",
            emoji="🟠",
        )

    if this_month:
        _render_urgency_section(
            "This Month",
            this_month,
            color="#f1c40f",
            emoji="🟡",
        )

    if upcoming:
        _render_urgency_section(
            "Upcoming",
            upcoming,
            color="#2ecc71",
            emoji="🟢",
        )

    if rolling:
        _render_urgency_section(
            "Rolling / Always Open",
            rolling,
            color="#95a5a6",
            emoji="🔵",
        )

    if not any([this_week, next_two_weeks, this_month, upcoming, rolling]):
        st.info("No upcoming deadlines found.")

    # Summary stats
    st.markdown("---")
    total_upcoming = len(this_week) + len(next_two_weeks) + len(this_month) + len(upcoming)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Due This Week", len(this_week))
    with col2:
        st.metric("Due This Month", len(this_week) + len(next_two_weeks) + len(this_month))
    with col3:
        st.metric("Total Upcoming", total_upcoming)


def _render_urgency_section(
    title: str,
    grants: list[Grant],
    color: str,
    emoji: str,
) -> None:
    """
    Render a section of grants grouped by urgency level.

    Args:
        title: Section title
        grants: Grants in this urgency group
        color: Accent color for the section
        emoji: Emoji indicator
    """
    st.markdown(
        f"""
        <div style="border-left: 4px solid {color}; padding-left: 12px; margin: 20px 0 10px 0;">
            <h4>{emoji} {title} ({len(grants)} grants)</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for grant in grants:
        days = grant.days_until_deadline
        deadline_str = grant.deadline.strftime("%b %d, %Y") if grant.deadline else "Open"

        if days is not None and days >= 0:
            countdown = f"**{days}** days left"
        elif days is not None and days < 0:
            countdown = "Expired"
        else:
            countdown = "No deadline"

        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

            with col1:
                st.markdown(f"**{grant.name}**")
                if grant.funder and grant.funder != grant.name:
                    st.caption(f"Funder: {grant.funder}")

            with col2:
                st.markdown(f"**{grant.amount_display}**")

            with col3:
                st.markdown(f"**{deadline_str}**")
                st.caption(countdown)

            with col4:
                if grant.url:
                    st.markdown(f"[Apply]({grant.url})")

            st.markdown("---")
