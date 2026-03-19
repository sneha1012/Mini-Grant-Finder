"""
Program matcher for mapping grants to Delta Rising Foundation's programs.

Uses keyword-based matching as a complement to TF-IDF scoring,
providing interpretable program assignments based on explicit
keyword hits rather than statistical similarity.
"""

import logging
import re
from pathlib import Path
from typing import Optional

import yaml

from src.models.grant import Grant

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"

# Program display names for user-facing output
PROGRAM_DISPLAY = {
    "ai_climate_tools": "AI Climate Tools",
    "resilience_nursery": "Resilience Nursery",
    "more_shade": "More Shade for More People",
    "cbecn": "CBECN",
}


class ProgramMatcher:
    """
    Matches grants to Delta Rising Foundation's 4 programs
    using keyword-based scoring.

    Each program has a set of keywords from config/keywords.yaml.
    A grant is matched to a program if its text contains enough
    of that program's keywords. The match quality is expressed as
    a confidence score (0.0 - 1.0).

    This provides more interpretable matches than TF-IDF alone
    and helps the team understand WHY a grant was recommended.
    """

    def __init__(self, keywords_path: Optional[str] = None):
        """
        Initialize the program matcher.

        Args:
            keywords_path: Path to keywords.yaml config file
        """
        self.keywords_path = keywords_path or str(
            CONFIG_DIR / "keywords.yaml"
        )
        self.program_keywords = self._load_keywords()
        self.cross_cutting_keywords = self._load_cross_cutting()

        logger.info(
            f"Program matcher initialized with {len(self.program_keywords)} programs"
        )

    def _load_keywords(self) -> dict[str, list[str]]:
        """Load program keywords from YAML config."""
        try:
            with open(self.keywords_path, "r") as f:
                config = yaml.safe_load(f)
        except (FileNotFoundError, yaml.YAMLError) as e:
            logger.error(f"Failed to load keywords: {e}")
            return {}

        programs = config.get("programs", {})
        result = {}
        for key, prog in programs.items():
            keywords = prog.get("keywords", [])
            # Add display name and description as bonus keywords
            if prog.get("display_name"):
                keywords.append(prog["display_name"].lower())
            if prog.get("description"):
                # Extract key phrases from description
                desc_words = prog["description"].lower().split()
                # Add 2-word phrases
                for i in range(len(desc_words) - 1):
                    phrase = f"{desc_words[i]} {desc_words[i+1]}"
                    if len(phrase) > 5:
                        keywords.append(phrase)
            result[key] = [kw.lower() for kw in keywords]

        return result

    def _load_cross_cutting(self) -> list[str]:
        """Load cross-cutting keywords."""
        try:
            with open(self.keywords_path, "r") as f:
                config = yaml.safe_load(f)
        except (FileNotFoundError, yaml.YAMLError):
            return []

        cross = config.get("cross_cutting", {})
        return [kw.lower() for kw in cross.get("keywords", [])]

    def match_grant(self, grant: Grant) -> dict[str, float]:
        """
        Match a single grant against all programs.

        Args:
            grant: Grant to match

        Returns:
            Dict mapping program keys to confidence scores (0.0-1.0)
        """
        grant_text = self._grant_to_text(grant)

        scores = {}
        for program, keywords in self.program_keywords.items():
            score = self._compute_match_score(grant_text, keywords)
            if score > 0:
                scores[program] = score

        return scores

    def match_grants(self, grants: list[Grant]) -> list[Grant]:
        """
        Match all grants to programs and update their matched_programs field.

        Args:
            grants: List of grants to match

        Returns:
            Updated grants with matched_programs set
        """
        for grant in grants:
            matches = self.match_grant(grant)

            # Sort by score and keep programs above threshold
            threshold = 0.1
            matched = [
                prog for prog, score in sorted(
                    matches.items(), key=lambda x: x[1], reverse=True
                )
                if score >= threshold
            ]

            grant.matched_programs = matched

        # Log summary
        matched_count = sum(1 for g in grants if g.matched_programs)
        logger.info(
            f"Program matching: {matched_count}/{len(grants)} grants "
            f"matched to at least one program"
        )

        return grants

    def _compute_match_score(
        self, text: str, keywords: list[str]
    ) -> float:
        """
        Compute keyword match score between text and keyword list.

        Uses a weighted approach:
        - Multi-word keyword matches count more (more specific)
        - More keyword hits = higher score
        - Score is normalized by total keyword count

        Args:
            text: The grant text to match against
            keywords: List of keywords for a program

        Returns:
            Match score from 0.0 to 1.0
        """
        if not text or not keywords:
            return 0.0

        text_lower = text.lower()
        total_weight = 0.0
        matched_weight = 0.0

        for keyword in keywords:
            # Multi-word keywords are weighted more (more specific matches)
            word_count = len(keyword.split())
            weight = word_count  # 1 for single words, 2 for bigrams, etc.
            total_weight += weight

            if keyword in text_lower:
                matched_weight += weight

        if total_weight == 0:
            return 0.0

        return matched_weight / total_weight

    def get_match_explanation(self, grant: Grant) -> dict[str, list[str]]:
        """
        Get a human-readable explanation of why a grant matches programs.

        Returns the specific keywords that matched for each program,
        so the team can understand the recommendation.

        Args:
            grant: Grant to explain

        Returns:
            Dict mapping program names to lists of matched keywords
        """
        grant_text = self._grant_to_text(grant)
        text_lower = grant_text.lower()

        explanations = {}
        for program, keywords in self.program_keywords.items():
            matched_keywords = [
                kw for kw in keywords if kw in text_lower
            ]
            if matched_keywords:
                display_name = PROGRAM_DISPLAY.get(program, program)
                explanations[display_name] = matched_keywords

        # Check cross-cutting keywords
        cross_matches = [
            kw for kw in self.cross_cutting_keywords if kw in text_lower
        ]
        if cross_matches:
            explanations["Cross-cutting themes"] = cross_matches

        return explanations

    def get_best_program(self, grant: Grant) -> Optional[str]:
        """
        Get the single best matching program for a grant.

        Args:
            grant: Grant to match

        Returns:
            Program display name or None if no match
        """
        matches = self.match_grant(grant)
        if not matches:
            return None

        best = max(matches, key=matches.get)
        return PROGRAM_DISPLAY.get(best, best)

    def get_cross_cutting_score(self, grant: Grant) -> float:
        """
        Score how well a grant matches cross-cutting themes.

        Args:
            grant: Grant to score

        Returns:
            Score from 0.0 to 1.0
        """
        return self._compute_match_score(
            self._grant_to_text(grant),
            self.cross_cutting_keywords,
        )

    def _grant_to_text(self, grant: Grant) -> str:
        """Combine grant text fields for matching."""
        parts = [
            grant.name,
            grant.description,
            " ".join(grant.focus_areas),
            grant.eligibility_notes,
            grant.geographic_scope,
            grant.funder,
        ]
        return " ".join(p for p in parts if p)


def match_grants_to_programs(grants: list[Grant]) -> list[Grant]:
    """
    Convenience function to match grants to Delta's programs.

    Args:
        grants: List of grants to match

    Returns:
        Updated grants with matched_programs set
    """
    matcher = ProgramMatcher()
    return matcher.match_grants(grants)
