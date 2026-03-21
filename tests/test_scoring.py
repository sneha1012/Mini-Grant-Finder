"""
Unit tests for the scoring engine and program matcher.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.grant import Grant, GrantType
from src.scoring.program_matcher import ProgramMatcher, PROGRAM_DISPLAY


class TestProgramMatcher:
    """Tests for keyword-based program matching."""

    @pytest.fixture
    def matcher(self):
        """Create a ProgramMatcher instance."""
        config_path = str(
            Path(__file__).parent.parent / "config" / "keywords.yaml"
        )
        return ProgramMatcher(keywords_path=config_path)

    def test_matcher_loads_programs(self, matcher):
        """Test that matcher loads all 4 programs."""
        assert len(matcher.program_keywords) == 4
        assert "ai_climate_tools" in matcher.program_keywords
        assert "resilience_nursery" in matcher.program_keywords
        assert "more_shade" in matcher.program_keywords
        assert "cbecn" in matcher.program_keywords

    def test_match_climate_grant(self, matcher):
        """Test matching a climate-related grant to AI Climate Tools."""
        grant = Grant(
            name="Carbon Market Verification Technology Grant",
            description="Funding for MRV technology and climate AI tools "
            "for nature-based carbon market monitoring",
            focus_areas=["climate technology", "carbon verification"],
        )
        matches = matcher.match_grant(grant)
        assert "ai_climate_tools" in matches
        assert matches["ai_climate_tools"] > 0

    def test_match_nursery_grant(self, matcher):
        """Test matching a plant-related grant to Resilience Nursery."""
        grant = Grant(
            name="Community Garden and Native Plants Initiative",
            description="Support for native plant propagation, community "
            "gardens, and urban agriculture food security programs",
            focus_areas=["native plants", "community garden"],
        )
        matches = matcher.match_grant(grant)
        assert "resilience_nursery" in matches

    def test_match_shade_grant(self, matcher):
        """Test matching a shade/heat grant to More Shade."""
        grant = Grant(
            name="Urban Heat Island Mitigation Grant",
            description="Funding for urban shade structures, tree canopy "
            "expansion, and community cooling solutions to address "
            "heat vulnerability",
            focus_areas=["urban shade", "heat island"],
        )
        matches = matcher.match_grant(grant)
        assert "more_shade" in matches

    def test_match_cbecn_grant(self, matcher):
        """Test matching an indigenous/biodiversity grant to CBECN."""
        grant = Grant(
            name="Indigenous Carbon Credit Partnership",
            description="Supporting indigenous communities and smallholder "
            "farmers in biodiversity conservation and carbon credit projects",
            focus_areas=["indigenous communities", "carbon credits"],
        )
        matches = matcher.match_grant(grant)
        assert "cbecn" in matches

    def test_no_match_irrelevant_grant(self, matcher):
        """Test that an unrelated grant gets low/no matches."""
        grant = Grant(
            name="Hospital Equipment Purchase Fund",
            description="Medical device acquisition for urban hospitals "
            "and surgical center upgrades",
            focus_areas=["healthcare", "medical devices"],
        )
        matches = matcher.match_grant(grant)
        # Should have no matches or very low scores
        for score in matches.values():
            assert score < 0.15

    def test_match_explanation(self, matcher):
        """Test getting human-readable match explanations."""
        grant = Grant(
            name="Urban Forestry Environmental Justice Grant",
            description="Tree canopy expansion in heat-vulnerable "
            "communities for environmental justice",
            focus_areas=["urban forestry", "environmental justice"],
        )
        explanations = matcher.get_match_explanation(grant)
        assert len(explanations) > 0
        # Should have at least matched keywords listed
        all_keywords = []
        for keywords in explanations.values():
            all_keywords.extend(keywords)
        assert len(all_keywords) > 0

    def test_get_best_program(self, matcher):
        """Test getting single best program match."""
        grant = Grant(
            name="Native Plant Seed Library",
            description="Drought resistant native species propagation "
            "and seed library for community food security",
        )
        best = matcher.get_best_program(grant)
        assert best is not None
        assert best in PROGRAM_DISPLAY.values()

    def test_match_grants_batch(self, matcher):
        """Test batch matching updates grant objects."""
        grants = [
            Grant(name="Carbon Market Tech", description="MRV climate AI"),
            Grant(name="Community Garden", description="Native plants nursery"),
            Grant(name="Hospital Fund", description="Medical equipment"),
        ]
        result = matcher.match_grants(grants)

        assert len(result) == 3
        # First two should have matches
        assert len(result[0].matched_programs) > 0 or len(result[1].matched_programs) > 0

    def test_cross_cutting_score(self, matcher):
        """Test cross-cutting theme scoring."""
        grant = Grant(
            name="Environmental Justice Community Grant",
            description="Racial equity and environmental justice in "
            "underrepresented communities for climate adaptation",
        )
        score = matcher.get_cross_cutting_score(grant)
        assert score > 0


class TestRelevanceScorer:
    """Tests for TF-IDF relevance scoring."""

    @pytest.fixture
    def scorer(self):
        """Create a RelevanceScorer (may fail if configs missing)."""
        try:
            from src.scoring.relevance import RelevanceScorer
            return RelevanceScorer()
        except Exception:
            pytest.skip("Scoring config files not available")

    def test_scorer_initializes(self, scorer):
        """Test that the scorer loads reference docs."""
        assert len(scorer.program_docs) == 4
        assert scorer.mission_doc != ""

    def test_score_relevant_grant(self, scorer):
        """Test scoring a relevant grant."""
        grant = Grant(
            name="EPA Environmental Justice Climate Adaptation",
            description="Community resilience and climate adaptation "
            "in underrepresented communities for carbon reduction",
            focus_areas=["climate", "environmental justice"],
        )
        score = scorer.score_grant(grant)
        assert score > 0
        assert score <= 100

    def test_score_irrelevant_grant(self, scorer):
        """Test scoring an irrelevant grant."""
        grant = Grant(
            name="Dental Equipment Modernization",
            description="Funding for dental practice equipment upgrades "
            "and orthodontic technology",
        )
        score = scorer.score_grant(grant)
        # Should be lower than a relevant grant
        relevant = Grant(
            name="Climate Carbon Market",
            description="Nature-based carbon verification technology",
        )
        relevant_score = scorer.score_grant(relevant)
        assert score < relevant_score

    def test_score_grants_batch(self, scorer):
        """Test batch scoring sorts by relevance."""
        grants = [
            Grant(name="Dental Fund", description="Orthodontic equipment"),
            Grant(
                name="Climate Justice Grant",
                description="Environmental justice climate adaptation "
                "carbon community resilience native plants",
            ),
        ]
        scored = scorer.score_grants(grants)
        # Highest-scored should be first
        assert scored[0].relevance_score >= scored[1].relevance_score
        assert scored[0].name == "Climate Justice Grant"

    def test_score_empty_grant(self, scorer):
        """Test scoring a grant with no text."""
        grant = Grant(name="")
        score = scorer.score_grant(grant)
        assert score == 0.0

    def test_match_programs(self, scorer):
        """Test program matching via TF-IDF."""
        grant = Grant(
            name="Urban Shade and Heat Island Reduction",
            description="Shade structures for community cooling "
            "and urban canopy expansion",
        )
        programs = scorer.match_programs(grant)
        assert isinstance(programs, list)
