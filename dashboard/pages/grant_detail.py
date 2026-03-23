"""
Grant detail view for the dashboard.

Shows comprehensive information about a selected grant including
eligibility, application instructions, matched programs, and
match explanation.
"""

import streamlit as st

from src.models.grant import Grant
from src.scoring.program_matcher import ProgramMatcher, PROGRAM_DISPLAY


def render_grant_detail(grants: list[Grant]) -> None:
    """
    Render the grant detail view.

    Users select a grant from a dropdown and see its full details
    including why it was matched to Delta's programs.

    Args:
        grants: List of all grants
    """
    st.markdown("### Grant Details")
    st.markdown("Select a grant to view full details and match explanation.")

    if not grants:
        st.info("No grants available.")
        return

    # Grant selector
    grant_names = [f"{g.name} (Score: {g.relevance_score:.0f})" for g in grants]
    selected_idx = st.selectbox(
        "Select a grant",
        range(len(grants)),
        format_func=lambda i: grant_names[i],
        key="detail_selector",
    )

    grant = grants[selected_idx]

    # Detail layout
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"## {grant.name}")

        if grant.url:
            st.markdown(f"[Visit Grant Page]({grant.url})")

        st.markdown("---")

        # Description
        if grant.description:
            st.markdown("#### Description")
            st.markdown(grant.description)

        # Eligibility
        if grant.eligibility_notes:
            st.markdown("#### Eligibility Requirements")
            st.markdown(grant.eligibility_notes)

        # How to Apply
        if grant.how_to_apply:
            st.markdown("#### How to Apply")
            st.markdown(grant.how_to_apply)

        # Focus Areas
        if grant.focus_areas:
            st.markdown("#### Focus Areas")
            st.markdown(" | ".join(f"`{fa}`" for fa in grant.focus_areas))

    with col2:
        # Key details card
        st.markdown("#### Quick Facts")

        st.markdown(
            f"""
            <div class="detail-card">
                <p><strong>Amount:</strong> {grant.amount_display}</p>
                <p><strong>Deadline:</strong> {_format_deadline_detail(grant)}</p>
                <p><strong>Status:</strong> {grant.status.value.replace('_', ' ').title()}</p>
                <p><strong>Type:</strong> {grant.grant_type.value.replace('_', ' ').title()}</p>
                <p><strong>Funder:</strong> {grant.funder}</p>
                <p><strong>Location:</strong> {grant.geographic_scope}</p>
                <p><strong>Source:</strong> {grant.source}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Relevance score
        score = grant.relevance_score
        score_color = (
            "#2d8a56" if score >= 70
            else "#d4800a" if score >= 40
            else "#c0392b"
        )
        st.markdown(
            f"""
            <div class="score-card" style="border-left: 4px solid {score_color};">
                <div class="score-value" style="color: {score_color};">
                    {score:.0f}
                </div>
                <div class="score-label">Relevance Score</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Matched programs
        if grant.matched_programs:
            st.markdown("#### Matched Programs")
            for prog in grant.matched_programs:
                display = PROGRAM_DISPLAY.get(prog, prog)
                st.markdown(f"- {display}")

        # Match explanation
        st.markdown("#### Why This Matches")
        try:
            matcher = ProgramMatcher()
            explanations = matcher.get_match_explanation(grant)

            if explanations:
                for program, keywords in explanations.items():
                    st.markdown(f"**{program}:**")
                    st.markdown(
                        ", ".join(f"`{kw}`" for kw in keywords[:5])
                    )
            else:
                st.markdown(
                    "*No specific keyword matches found. "
                    "Score is based on general text similarity.*"
                )
        except Exception:
            st.markdown("*Match explanation unavailable*")


def _format_deadline_detail(grant: Grant) -> str:
    """Format deadline with full detail."""
    if grant.deadline:
        date_str = grant.deadline.strftime("%B %d, %Y")
        days = grant.days_until_deadline
        if days is not None:
            if days < 0:
                return f"{date_str} (expired {abs(days)} days ago)"
            elif days == 0:
                return f"{date_str} (TODAY!)"
            elif days <= 7:
                return f"{date_str} ({days} days remaining)"
            elif days <= 30:
                return f"{date_str} ({days} days)"
            return date_str
    return grant.deadline_text if grant.deadline_text else "Not specified"
