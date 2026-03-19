"""
TF-IDF relevance scoring engine for grant matching.

Uses scikit-learn's TfidfVectorizer to compute cosine similarity
between grant descriptions and Delta Rising Foundation's mission/programs.
Runs entirely locally — no API calls, no costs.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.models.grant import Grant

logger = logging.getLogger(__name__)

# Path to config files
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class RelevanceScorer:
    """
    Scores grants by relevance to Delta Rising Foundation's mission.

    Uses TF-IDF vectorization and cosine similarity to compare each
    grant's text (name + description + focus areas) against Delta's
    mission statement and program descriptions.

    Scoring scale: 0-100 (higher = more relevant)
    """

    def __init__(
        self,
        profile_path: Optional[str] = None,
        keywords_path: Optional[str] = None,
    ):
        """
        Initialize the scoring engine.

        Loads organization profile and keywords from YAML config files
        to build the reference corpus that grants are scored against.

        Args:
            profile_path: Path to delta_profile.yaml
            keywords_path: Path to keywords.yaml
        """
        self.profile_path = profile_path or str(
            CONFIG_DIR / "delta_profile.yaml"
        )
        self.keywords_path = keywords_path or str(
            CONFIG_DIR / "keywords.yaml"
        )

        # Load profile and keyword data
        self.profile = self._load_yaml(self.profile_path)
        self.keywords = self._load_yaml(self.keywords_path)

        # Build reference documents for each program
        self.program_docs = self._build_program_docs()
        self.mission_doc = self._build_mission_doc()

        # Initialize TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=5000,
            ngram_range=(1, 2),  # Unigrams and bigrams
            min_df=1,
            sublinear_tf=True,
        )

        # Fit the vectorizer on reference documents
        all_docs = [self.mission_doc] + list(self.program_docs.values())
        self.vectorizer.fit(all_docs)

        # Pre-compute reference vectors
        self.mission_vector = self.vectorizer.transform([self.mission_doc])
        self.program_vectors = {
            name: self.vectorizer.transform([doc])
            for name, doc in self.program_docs.items()
        }

        logger.info(
            f"Relevance scorer initialized with {len(self.program_docs)} "
            f"program profiles"
        )

    def _load_yaml(self, filepath: str) -> dict:
        """Load a YAML configuration file."""
        try:
            with open(filepath, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Config file not found: {filepath}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {filepath}: {e}")
            return {}

    def _build_mission_doc(self) -> str:
        """
        Build a reference document from the organization's mission,
        vision, and focus areas.
        """
        parts = []

        org = self.profile.get("organization", {})
        if org.get("mission"):
            parts.append(org["mission"])
        if org.get("vision"):
            parts.append(org["vision"])
        if org.get("focus_areas"):
            parts.append(" ".join(org["focus_areas"]))

        # Add cross-cutting keywords
        cross = self.keywords.get("cross_cutting", {})
        if cross.get("keywords"):
            parts.append(" ".join(cross["keywords"]))

        return " ".join(parts)

    def _build_program_docs(self) -> dict[str, str]:
        """
        Build reference documents for each Delta Rising program.

        Combines program descriptions from the profile with
        program-specific keywords from the keywords config.
        """
        docs = {}

        # From profile
        programs = self.profile.get("programs", {})
        # From keywords
        kw_programs = self.keywords.get("programs", {})

        all_program_keys = set(programs.keys()) | set(kw_programs.keys())

        for key in all_program_keys:
            parts = []

            # Profile data
            prog = programs.get(key, {})
            if prog.get("name"):
                parts.append(prog["name"])
            if prog.get("description"):
                parts.append(prog["description"])

            # Keywords data
            kw_prog = kw_programs.get(key, {})
            if kw_prog.get("display_name"):
                parts.append(kw_prog["display_name"])
            if kw_prog.get("description"):
                parts.append(kw_prog["description"])
            if kw_prog.get("keywords"):
                parts.append(" ".join(kw_prog["keywords"]))

            if parts:
                docs[key] = " ".join(parts)

        return docs

    def score_grant(self, grant: Grant) -> float:
        """
        Compute a relevance score for a single grant.

        The score is a weighted combination of:
        - Mission alignment (cosine similarity to mission doc)
        - Best program match (highest cosine similarity to any program)

        Args:
            grant: Grant to score

        Returns:
            Relevance score from 0 to 100
        """
        grant_text = self._grant_to_text(grant)

        if not grant_text.strip():
            return 0.0

        try:
            grant_vector = self.vectorizer.transform([grant_text])
        except Exception as e:
            logger.debug(f"Vectorization failed for '{grant.name}': {e}")
            return 0.0

        # Mission alignment score
        mission_sim = cosine_similarity(
            grant_vector, self.mission_vector
        )[0][0]

        # Best program match score
        best_program_sim = 0.0
        for _name, pvec in self.program_vectors.items():
            sim = cosine_similarity(grant_vector, pvec)[0][0]
            if sim > best_program_sim:
                best_program_sim = sim

        # Weighted combination (mission 60%, best program 40%)
        raw_score = (mission_sim * 0.6) + (best_program_sim * 0.4)

        # Scale to 0-100 range
        # Cosine similarity typically ranges 0-0.5 for this kind of comparison
        # Scale so that 0.3+ maps to ~80+
        scaled = min(raw_score * 250, 100)

        return round(scaled, 1)

    def score_grants(self, grants: list[Grant]) -> list[Grant]:
        """
        Score all grants and update their relevance_score field.

        Also updates matched_programs and priority based on scores.

        Args:
            grants: List of grants to score

        Returns:
            Same list with updated relevance_score fields
        """
        for grant in grants:
            grant.relevance_score = self.score_grant(grant)
            grant.matched_programs = self.match_programs(grant)
            grant.update_priority()

        # Sort by relevance score (highest first)
        grants.sort(key=lambda g: g.relevance_score, reverse=True)

        logger.info(
            f"Scored {len(grants)} grants. "
            f"Top score: {grants[0].relevance_score if grants else 0}. "
            f"Median: {grants[len(grants)//2].relevance_score if grants else 0}"
        )

        return grants

    def match_programs(self, grant: Grant) -> list[str]:
        """
        Determine which Delta programs a grant matches best.

        Returns programs where the cosine similarity exceeds
        the matching threshold.

        Args:
            grant: Grant to match

        Returns:
            List of matching program keys (e.g., ['resilience_nursery', 'more_shade'])
        """
        grant_text = self._grant_to_text(grant)
        if not grant_text.strip():
            return []

        try:
            grant_vector = self.vectorizer.transform([grant_text])
        except Exception:
            return []

        matches = []
        threshold = 0.05  # Minimum similarity to count as a match

        for name, pvec in self.program_vectors.items():
            sim = cosine_similarity(grant_vector, pvec)[0][0]
            if sim >= threshold:
                matches.append((name, sim))

        # Sort by similarity and return program names
        matches.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _sim in matches]

    def _grant_to_text(self, grant: Grant) -> str:
        """
        Convert a Grant to a text document for TF-IDF comparison.

        Combines all relevant text fields into a single string.
        """
        parts = [
            grant.name,
            grant.description,
            " ".join(grant.focus_areas),
            grant.eligibility_notes,
            grant.geographic_scope,
            grant.funder,
        ]
        return " ".join(p for p in parts if p)


def score_grants(grants: list[Grant]) -> list[Grant]:
    """
    Convenience function to score grants using default configuration.

    Args:
        grants: List of grants to score

    Returns:
        Scored and sorted grants
    """
    scorer = RelevanceScorer()
    return scorer.score_grants(grants)
